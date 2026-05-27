"""Authentication: OAuth2 client-credentials token provider + keychain helpers."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Callable, Optional

import httpx
import jwt

logger = logging.getLogger(__name__)

_SERVICE_NAME = "TikiTakaPAYDWH"
_ACCOUNT_NAME = "default"
_KEYRING_FALLBACK_FILE_ENV = "TIKITAKA_CRED_FILE"


# ---------------------------------------------------------------------------
# Keychain helpers
# ---------------------------------------------------------------------------


def save_credentials(username: str, password: str) -> None:
    """Persist username and password to OS keychain (or encrypted fallback)."""
    try:
        import keyring

        keyring.set_password(_SERVICE_NAME, f"{_ACCOUNT_NAME}:username", username)
        keyring.set_password(_SERVICE_NAME, f"{_ACCOUNT_NAME}:password", password)
        logger.info("Credentials saved to OS keychain.")
    except Exception:
        logger.warning("Keyring unavailable — using encrypted file fallback.", exc_info=True)
        _file_save(username, password)


def load_credentials() -> tuple[str, str] | None:
    """Return (username, password) or None if not stored."""
    try:
        import keyring

        username = keyring.get_password(_SERVICE_NAME, f"{_ACCOUNT_NAME}:username")
        password = keyring.get_password(_SERVICE_NAME, f"{_ACCOUNT_NAME}:password")
        if username and password:
            return username, password
    except Exception:
        logger.warning("Keyring unavailable — trying file fallback.", exc_info=True)
    return _file_load()


def clear_credentials() -> None:
    """Remove stored credentials from keychain and fallback file."""
    try:
        import keyring

        keyring.delete_password(_SERVICE_NAME, f"{_ACCOUNT_NAME}:username")
        keyring.delete_password(_SERVICE_NAME, f"{_ACCOUNT_NAME}:password")
    except Exception:
        pass
    _file_clear()


# ---------------------------------------------------------------------------
# Encrypted file fallback (used when keyring has no backend)
# ---------------------------------------------------------------------------


def _fallback_path() -> Path:
    env = os.environ.get(_KEYRING_FALLBACK_FILE_ENV)
    if env:
        return Path(env)
    from tikitaka_dwh.config import get_settings

    return get_settings().app_data_dir / ".credentials.enc"


def _derive_key(passphrase: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode(), b"tikitaka-dwh-salt", 200_000)


def _get_fernet_key() -> bytes:
    """Return a Fernet-ready key.

    Priority:
    1. TIKITAKA_CRED_PASSPHRASE env var (enterprise deployments / MDM-managed).
    2. Per-machine random key stored in .credentials.key (generated on first use).
    """
    from cryptography.fernet import Fernet

    passphrase = os.environ.get("TIKITAKA_CRED_PASSPHRASE")
    if passphrase:
        return base64.urlsafe_b64encode(_derive_key(passphrase))

    key_path = _fallback_path().with_suffix(".key")
    if key_path.exists():
        raw = key_path.read_bytes()
        if len(raw) == 32:
            return base64.urlsafe_b64encode(raw)
        logger.warning("Credential key file is corrupt — regenerating.")

    raw = secrets.token_bytes(32)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(raw)
    try:
        key_path.chmod(0o600)
    except AttributeError:
        pass  # Windows does not support POSIX chmod
    logger.info("Generated new per-machine credential key at %s", key_path)
    return base64.urlsafe_b64encode(raw)


def _file_save(username: str, password: str) -> None:
    from cryptography.fernet import Fernet

    fernet = Fernet(_get_fernet_key())
    payload = f"{username}\n{password}".encode()
    encrypted = fernet.encrypt(payload)
    path = _fallback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypted)
    try:
        path.chmod(0o600)
    except AttributeError:
        pass  # Windows does not support POSIX chmod
    logger.info("Credentials saved to encrypted file fallback: %s", path)


def _file_load() -> tuple[str, str] | None:
    path = _fallback_path()
    if not path.exists():
        return None
    try:
        from cryptography.fernet import Fernet, InvalidToken

        fernet = Fernet(_get_fernet_key())
        decrypted = fernet.decrypt(path.read_bytes()).decode()
        cid, csec = decrypted.split("\n", 1)
        return cid, csec
    except (InvalidToken, ValueError) as exc:
        logger.error("Failed to decrypt credentials file: %s", exc)
        return None


def _file_clear() -> None:
    path = _fallback_path()
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# Token provider
# ---------------------------------------------------------------------------


class TokenProvider:
    """Manages OAuth2 client-credentials access tokens, refreshing before expiry."""

    _REFRESH_BEFORE_EXPIRY_S = 60

    def __init__(
        self,
        username_provider: Callable[[], str],
        password_provider: Callable[[], str],
        base_url: str,
        http_client: httpx.AsyncClient,
    ) -> None:
        self._username_fn = username_provider
        self._password_fn = password_provider
        self._base_url = base_url.rstrip("/")
        self._http = http_client
        self._token: Optional[str] = None
        self._exp: float = 0.0

    async def get_token(self) -> str:
        if self._token and time.time() < self._exp - self._REFRESH_BEFORE_EXPIRY_S:
            return self._token
        await self._fetch_token()
        assert self._token is not None
        return self._token

    def invalidate(self) -> None:
        self._token = None
        self._exp = 0.0

    async def _fetch_token(self) -> None:
        resp = await self._http.post(
            f"{self._base_url}/clients/token",
            data={
                "grant_type": "",
                "username": self._username_fn(),
                "password": self._password_fn(),
                "scope": "",
                "client_id": "",
                "client_secret": "",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        body = resp.json()
        token = body["access_token"]
        try:
            claims = jwt.decode(token, options={"verify_signature": False})
            self._exp = float(claims["exp"])
        except Exception:
            # Fallback: assume expires_in seconds from now
            expires_in = int(body.get("expires_in", 3600))
            self._exp = time.time() + expires_in
        self._token = token
        logger.debug("Token refreshed, expires at %s", self._exp)
