# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for Tiki-Taka PAY DWH — one-folder build.
#
# Build:
#   uv run pyinstaller packaging/pyinstaller.spec
#
# Output: dist/TikiTakaPAYDWH/  (folder with executable + all deps)

import sys
from pathlib import Path
import importlib.util
from PyInstaller.utils.hooks import copy_metadata

# SPECPATH is set by PyInstaller to the directory containing this .spec file
# (i.e. packaging/).  Go one level up to reach the repo root.
ROOT = Path(SPECPATH).parent
SRC = ROOT / "src" / "tikitaka_dwh"

# ── Locate Streamlit's static assets ────────────────────────────────────────
streamlit_spec = importlib.util.find_spec("streamlit")
if streamlit_spec is None or streamlit_spec.origin is None:
    raise RuntimeError("streamlit not installed in current environment")
STREAMLIT_DIR = Path(streamlit_spec.origin).parent

# ── Locate DuckDB shared library ─────────────────────────────────────────────
duckdb_spec = importlib.util.find_spec("duckdb")
if duckdb_spec is None or duckdb_spec.origin is None:
    raise RuntimeError("duckdb not installed in current environment")
DUCKDB_DIR = Path(duckdb_spec.origin).parent

# ── Hidden imports needed at runtime ────────────────────────────────────────
hidden = [
    # Streamlit components
    "streamlit",
    "streamlit.web.cli",
    "streamlit.web.bootstrap",
    "streamlit.runtime.scriptrunner.magic_funcs",
    # DuckDB
    "duckdb",
    # Pydantic v2
    "pydantic",
    "pydantic_settings",
    "pydantic.deprecated.decorator",
    # Data stack
    "pandas",
    "pyarrow",
    "pyarrow.parquet",
    # Auth / crypto
    "keyring",
    "keyring.backends",
    "keyring.backends.Windows",
    "keyring.backends.SecretService",
    "keyring.backends.OS_X",
    "jwt",
    "cryptography",
    "cryptography.fernet",
    # App modules
    "tikitaka_dwh",
    "tikitaka_dwh.config",
    "tikitaka_dwh.auth",
    "tikitaka_dwh.api.client",
    "tikitaka_dwh.api.schemas",
    "tikitaka_dwh.sync.engine",
    "tikitaka_dwh.sync.watermark",
    "tikitaka_dwh.sync.raw_writer",
    "tikitaka_dwh.transform.decode",
    "tikitaka_dwh.transform.documents",
    "tikitaka_dwh.transform.sale_lines",
    "tikitaka_dwh.transform.payments",
    "tikitaka_dwh.transform.dimensions",
    "tikitaka_dwh.warehouse.db",
    "tikitaka_dwh.warehouse.migrations.runner",
    "tikitaka_dwh.ui.app",
    "tikitaka_dwh.ui.i18n",
    "tikitaka_dwh.ui.onboarding",
    "tikitaka_dwh.ui.settings",
    "tikitaka_dwh.ui.diagnostics",
    "tikitaka_dwh.ui.components",
    "tikitaka_dwh.ui.pages.01_revenue",
    "tikitaka_dwh.ui.pages.02_products",
    "tikitaka_dwh.ui.pages.03_stores_pos",
    "tikitaka_dwh.ui.pages.04_heatmap",
    "tikitaka_dwh.ui.pages.05_vat",
    "tikitaka_dwh.ui.pages.06_z_reports",
    "tikitaka_dwh.observability.logging",
    "tikitaka_dwh.observability.sentry",
    # Misc runtime deps
    "httpx",
    "platformdirs",
    "pytz",
    "sentry_sdk",
    "openpyxl",
    "dateutil",
]

# ── Data files (non-Python assets bundled into the build) ────────────────────
datas = [
    # Streamlit static + component assets
    (str(STREAMLIT_DIR / "static"),        "streamlit/static"),
    (str(STREAMLIT_DIR / "components"),    "streamlit/components"),
    # SQL migration files
    (str(SRC / "warehouse" / "migrations"), "tikitaka_dwh/warehouse/migrations"),
    # ui/app.py must be a physical file on disk — Streamlit reads and executes it
    (str(SRC / "ui" / "app.py"),           "tikitaka_dwh/ui"),
]
# Include dist-info for every package that calls importlib.metadata.version() at
# import time.  Missing dist-info raises PackageNotFoundError and crashes silently
# (console=False).  Copy metadata for the whole direct-dependency set to be safe.
for _pkg in [
    "streamlit", "altair", "click", "watchdog", "tornado",
    "pydantic", "pydantic-core", "pydantic-settings",
    "httpx", "httpcore", "anyio", "starlette",
    "pandas", "pyarrow", "duckdb", "openpyxl",
    "cryptography", "keyring", "platformdirs",
    "python-dateutil", "PyJWT", "pytz",
    "sentry-sdk", "rich", "packaging", "Pillow",
]:
    try:
        datas += copy_metadata(_pkg)
    except Exception:
        pass

# ── Binary extensions ─────────────────────────────────────────────────────────
binaries = []
# On Windows, DuckDB ships as a .pyd; PyInstaller usually finds it, but list explicitly
for ext in ("*.pyd", "*.so", "*.dll"):
    for p in DUCKDB_DIR.glob(ext):
        binaries.append((str(p), "."))

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [str(SRC / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "respx", "freezegun", "mypy", "ruff", "pyinstaller"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TikiTakaPAYDWH",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / "packaging" / "windows" / "icon.ico") if (ROOT / "packaging" / "windows" / "icon.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TikiTakaPAYDWH",
)
