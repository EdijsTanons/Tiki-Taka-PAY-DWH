"""Application settings and directory management."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_dir
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TIKITAKA_", env_file=".env", extra="ignore")

    api_base_url: str = "https://api.manage.tikitaka.lv"
    app_data_dir: Path = Path(user_data_dir("TikiTakaPAYDWH", appauthor=False))
    sentry_dsn: str | None = None
    log_level: str = "INFO"

    @field_validator("app_data_dir", mode="before")
    @classmethod
    def coerce_path(cls, v: object) -> Path:
        return Path(str(v))


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def ensure_app_dirs(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    for sub in ("lake/raw", "lake/staging", "logs"):
        (s.app_data_dir / sub).mkdir(parents=True, exist_ok=True)
