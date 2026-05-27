"""Tests for config.py — ensure_app_dirs is idempotent."""

from pathlib import Path

from tikitaka_dwh.config import Settings, ensure_app_dirs


def test_ensure_app_dirs_creates_subdirs(tmp_path: Path):
    settings = Settings(app_data_dir=tmp_path / "data")
    ensure_app_dirs(settings)

    assert (tmp_path / "data" / "lake" / "raw").is_dir()
    assert (tmp_path / "data" / "lake" / "staging").is_dir()
    assert (tmp_path / "data" / "logs").is_dir()


def test_ensure_app_dirs_idempotent(tmp_path: Path):
    settings = Settings(app_data_dir=tmp_path / "data")
    ensure_app_dirs(settings)
    ensure_app_dirs(settings)  # second call must not raise
    assert (tmp_path / "data" / "logs").is_dir()
