# Tiki-Taka PAY DWH

Offline-first analytics dashboard for Tikitaka POS clients.
Pulls fiscal documents from the Tikitaka REST API, stores them locally as
Parquet + DuckDB, and shows five dashboards through a packaged desktop app.

All customer data stays on the user's laptop — no cloud, no telemetry.

---

## Quick start (development)

```bash
# 1. Install dependencies
python -m uv sync --dev

# 2. Run the UI (opens browser automatically)
uv run python -m tikitaka_dwh

# — or — run the sync CLI without UI
uv run python scripts/dev_sync.py --mode backfill
uv run python scripts/dev_sync.py --mode incremental
```

## Run tests

```bash
uv run pytest
```

## Build a distributable

```bash
# Current platform (Windows / macOS / Linux)
uv run python scripts/build.py

# Specific platform
uv run python scripts/build.py --platform windows
```

See `packaging/macos/README.md` for macOS codesigning steps.

## Reset local data (re-backfill)

```bash
uv run python scripts/reset_warehouse.py
```

---

## Project layout

```
src/tikitaka_dwh/
├── __main__.py          # launches Streamlit
├── config.py            # settings + app-data dir
├── auth.py              # OAuth2 token provider + keychain
├── api/                 # httpx client + pydantic schemas
├── sync/                # backfill / incremental engine
├── transform/           # decode, documents, sale_lines, payments, dims
├── warehouse/           # DuckDB migrations + loader
├── ui/                  # Streamlit app shell + 5 pages
└── observability/       # logging + Sentry
```

## Data flow

```
Tikitaka API
    │  HTTPS (OAuth2 bearer)
    ▼
lake/raw/dt=YYYY-MM-DD/*.json     ← append-only, one file per page
    │
    ▼  transform (pandas)
lake/staging/documents/…/*.parquet
    │
    ▼  DuckDB upsert
warehouse.duckdb
    ├── fct_documents
    ├── fct_sale_lines
    ├── fct_payments
    ├── dim_*
    └── agg_*              ← rebuilt after every sync
    │
    ▼
Streamlit dashboards
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `TIKITAKA_API_BASE_URL` | `https://api.manage.tikitaka.lv` | API endpoint |
| `TIKITAKA_APP_DATA_DIR` | platform default | Override data folder |
| `TIKITAKA_SENTRY_DSN` | *(unset)* | Enable crash reporting |
| `TIKITAKA_LOG_LEVEL` | `INFO` | Log level |
| `TIKITAKA_CRED_PASSPHRASE` | *(insecure default)* | Passphrase for credential file fallback |
| `TIKITAKA_E2E=1` | *(unset)* | Enable live-API integration tests |
