# TikiTaka PAY DWH

Offline-first analytics desktop app for Tiki-Taka PAY POS clients: syncs documents from the Tikitaka API into a local DuckDB warehouse and shows Streamlit dashboards. Packaged as a Windows exe (PyInstaller + NSIS). All data stays local — no cloud, no telemetry.

## Commands

`uv` is NOT on PATH on this machine — use the venv binaries directly:

- Tests: `.venv\Scripts\pytest.exe --tb=short -q` (all must pass, none skipped)
- Lint: `.venv\Scripts\python.exe -m ruff check src scripts tests` (keep it clean)
- Types: `.venv\Scripts\python.exe -m mypy src` (strict; keep it green)
- Run app: `.venv\Scripts\python.exe -m tikitaka_dwh`
- Headless sync: `.venv\Scripts\python.exe scripts\dev_sync.py --mode backfill`
- Build: `.venv\Scripts\python.exe scripts\build.py` (PyInstaller → NSIS)
- Release: `/ship` slash command (test → build → NSIS → commit → push)

CI (`.github/workflows/ci.yml`) runs ruff + mypy + pytest on windows-latest for every push/PR.

## Architecture

Data flow: API (OAuth2, descending doc-ID order) → `lake/raw/dt=*/​*.json` (append-only) → pandas transform → `lake/staging/*.parquet` → DuckDB upsert (`warehouse.duckdb`) → Streamlit pages.

- `sync/engine.py` — resumable backfill (checkpoint every 1000 docs) + incremental mode; `sync/watermark.py` stores the cursor/peak/watermark in the `_sync_state` table. The watermark is the highest doc ID seen; resume logic depends on the API's DESC ordering.
- `transform/` — builds fct_documents / fct_sale_lines / fct_payments + dims from raw dicts; `decode.py` parses the POS XML in the `doc` field.
- `warehouse/db.py` — upsert loader and `rebuild_from_raw` (must never advance the watermark when raw files are unreadable — `failed_files` in the stats dict guards this).
- `ui/` — app shell + 6 pages. ALL user-facing strings go through `ui/i18n.py` `t(key)`; every new key must be added to all four dicts (EN/LV/LT/ET).
- `ui/components.py query()` is cached with `st.cache_data` — call `st.cache_data.clear()` after any sync or warehouse load.

## Gotchas

- Version lives in 5 files — never edit by hand; run `python scripts/bump_version.py X.Y.Z`.
- New `tikitaka_dwh.*` modules MUST be added to the `hidden` list in `packaging/pyinstaller.spec`, or the packaged exe crashes silently at runtime.
- Data dir (`%LOCALAPPDATA%\TikiTakaPAYDWH`) is separate from the install dir (`%LOCALAPPDATA%\Programs\TikiTakaPAYDWH`); the installer/uninstaller must never touch the data dir.
- DuckDB `DAYOFWEEK` returns Sunday=0 — use `ISODOW` (Mon=1 … Sun=7).
- `doc_datetime_local` is the raw API string; `doc_datetime_utc` is naive UTC converted via Europe/Riga with `is_dst=False` (deterministic during DST folds).
- HTTP in tests is mocked with `respx`; transform tests use `tests/fixtures/sample_response.json`.
- ruff `allowed-confusables` permits typographic – − ‘ ’ × in UI strings — don't "fix" them to ASCII.
