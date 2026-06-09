# TikiTaka PAY DWH

**Version 0.2.0**

Offline-first analytics desktop application for Tiki-Taka PAY clients. All data stays local — no cloud, no telemetry.

**Stack:** Streamlit UI · DuckDB warehouse · PyInstaller Windows exe · NSIS installer · Python 3.11+ · `uv`

---

## Project layout

```
src/tikitaka_dwh/
├── __main__.py          # launches Streamlit
├── config.py            # settings + app-data dir
├── auth.py              # OAuth2 token provider + keychain
├── api/                 # httpx client + pydantic schemas
├── sync/                # backfill / incremental engine + watermark
├── transform/           # decode, documents, sale_lines, payments, dims
├── warehouse/           # DuckDB migrations + loader
├── ui/                  # Streamlit app shell + 6 analytics pages + diagnostics
└── observability/       # logging + Sentry

scripts/
├── build.py             # cross-platform PyInstaller + NSIS build
├── build_from_raw.py    # load raw JSON lake → warehouse (large initial syncs)
├── dev_sync.py          # headless sync CLI
├── reset_warehouse.py   # wipe and restart
└── create_icons.py      # generate icon assets
```

---

## Data flow

```
Tikitaka API  (OAuth2 HTTPS)
    │
    ▼
lake/raw/dt=YYYY-MM-DD/*.json        append-only, one file per API page
    │                                 safe on disk even if sync is interrupted
    ▼  transform (pandas)
lake/staging/documents|sale_lines|payments/*.parquet
    │
    ▼  DuckDB upsert
warehouse.duckdb
    ├── fct_documents / fct_sale_lines / fct_payments
    ├── dim_store / dim_pos / dim_operator / dim_product / dim_customer
    ├── agg_daily_revenue / agg_product_daily / agg_hourly
    └── _sync_state (watermark + backfill resume cursor)
    │
    ▼
Streamlit dashboards (6 pages)
```

---

## Sync modes

- **Backfill** — downloads all documents from the beginning, checkpointing every 1 000 docs so it safely resumes after a sleep or crash
- **Incremental** — fetches only documents newer than the last watermark ID

---

## Development

```bash
uv sync --dev
uv run python -m tikitaka_dwh               # launch UI
uv run python scripts/dev_sync.py --mode backfill
uv run pytest
```

---

## Build

```bash
# PyInstaller + NSIS in one step (Windows)
uv run python scripts/build.py

# or individually:
uv run pyinstaller packaging/pyinstaller.spec --noconfirm
makensis packaging\windows\installer.nsi
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `TIKITAKA_API_BASE_URL` | `https://api.manage.tikitaka.lv` | API endpoint |
| `TIKITAKA_APP_DATA_DIR` | platform default | Override data folder |
| `TIKITAKA_SENTRY_DSN` | *(unset)* | Enable crash reporting |
| `TIKITAKA_LOG_LEVEL` | `INFO` | Log level |

---

## Changelog

### Unreleased

- **fix(ui):** Sunday sales no longer show as "?" in the heatmap — `DAYOFWEEK` (Sunday = 0) replaced with `ISODOW` (Monday = 1 … Sunday = 7)
- **fix(ui):** dashboard SQL errors are now logged instead of silently rendering as "no data"
- **fix(transform):** documents timestamped inside the autumn DST fold no longer lose their UTC timestamp (`is_dst=False` instead of raising on ambiguous times)
- **fix(sync):** backfill checkpoint (skip cursor + peak ID) is now written in a single transaction — a crash can no longer shrink the final watermark
- **fix(warehouse):** `audit_raw` / `rebuild_from_raw` now report `failed_files`; the watermark is never advanced when raw files could not be read (UI and `build_from_raw.py` surface a warning)
- **fix(i18n):** onboarding 401 error, "Navigate" label and page-load errors are now translated; rebuild result messages survive the page rerun
- **fix(security):** Sentry events are now scrubbed recursively (breadcrumbs, extra, exception values) with local variables disabled; the log filter also redacts bearer tokens/JWTs in positional `%s` args
- **fix(installer):** upgrades now wipe the previous version's files first (guarded by the uninstaller's presence) — stale PyInstaller DLLs no longer survive an update
- **perf(ui):** dashboard queries are cached (`st.cache_data`, 5 min TTL, cleared after every sync/load)
- **chore:** GitHub Actions CI (`ruff` + `mypy --strict` + `pytest` on windows-latest); the repo is now ruff- and mypy-clean
- **chore:** `scripts/bump_version.py` updates the version in all 5 source/packaging locations in one command; macOS/Linux packaging re-synced to the current version
- **test:** API client (pagination, watermark stop, retry, re-auth, 500-recovery), migration runner and log/Sentry scrubbing are now covered
- **chore:** removed leftover debug scripts (`scripts/_inspect_z*.py`, `_test_z_parser.py`); added `CLAUDE.md`

### 0.2.0

- **fix:** staging write failure now fails the sync instead of silently advancing the watermark (potential data-loss bug)
- **feat:** resumable backfill — checkpoints every 1 000 docs; a sleep/crash loses at most that many docs of work
- **feat:** `scripts/build_from_raw.py` — load whatever raw JSON is already on disk into the warehouse without re-downloading; `--audit-only` to count duplicates without writing
- **feat:** Diagnostics page now shows raw-data stats (file count, unique IDs, duplicate count) and a "Rebuild from raw" button
- **fix(installer):** NSIS installer now force-closes the running app before overwriting DLLs; adds `VersionMajor`/`VersionMinor` registry keys

### 0.1.0

- Initial release
