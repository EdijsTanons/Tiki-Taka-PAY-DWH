# Tiki-Taka PAY DWH — User Guide

**Version 0.2.0**

---

## Table of contents

1. [What is Tiki-Taka PAY DWH?](#1-what-is-tiki-taka-pay-dwh)
2. [How it works](#2-how-it-works)
3. [First-time setup](#3-first-time-setup)
   - [Installation](#installation)
   - [Onboarding wizard](#onboarding-wizard)
   - [Large initial syncs](#large-initial-syncs)
4. [The interface](#4-the-interface)
5. [Everyday features](#5-everyday-features)
   - [5.1 Revenue](#51-revenue)
   - [5.2 Products](#52-products)
   - [5.3 Stores & POS](#53-stores--pos)
   - [5.4 Heatmap — Peak Times](#54-heatmap--peak-times)
   - [5.5 VAT Summary](#55-vat-summary)
   - [5.6 Z Reports](#56-z-reports)
6. [Keeping data up to date](#6-keeping-data-up-to-date)
   - [Manual sync](#manual-sync)
   - [What happens during a sync](#what-happens-during-a-sync)
   - [Resume after interruption](#resume-after-interruption)
   - [If a sync fails](#if-a-sync-fails)
7. [Administration](#7-administration)
   - [7.1 Settings](#71-settings)
   - [7.2 Diagnostics](#72-diagnostics)
   - [7.3 Command-line tools](#73-command-line-tools)
8. [Upgrading to a new version](#8-upgrading-to-a-new-version)
9. [Configuration reference](#9-configuration-reference)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. What is Tiki-Taka PAY DWH?

Tiki-Taka PAY DWH is a desktop analytics application for businesses running the Tikitaka point-of-sale system. It downloads your transaction data from the Tikitaka API and stores it in a local database on your computer, then presents it through a set of interactive dashboards.

Key properties:

- **Offline-first.** Once data is downloaded, every dashboard and report works without an internet connection.
- **Local only.** Your data never leaves your machine. There is no cloud sync, no shared server, and no telemetry unless you explicitly configure a Sentry DSN for crash reporting.
- **Resumable.** Large downloads checkpoint every 1 000 documents, so a laptop sleep or network drop never loses all your progress.
- **Self-contained.** The application ships as a single Windows installer and requires no Python or database installation.

---

## 2. How it works

```
Tikitaka API  (your credentials, HTTPS)
      │
      ▼
  Raw JSON files on disk  ──  safe even if sync is interrupted
      │
      ▼
  Staging Parquet files   ──  transformed by pandas
      │
      ▼
  Local DuckDB database   ──  warehouse.duckdb
      │
      ▼
  Streamlit dashboards    ──  6 analytics pages in your browser
```

The application runs a small local web server and opens your default browser to display the dashboards. Nothing is sent to an external server.

**Sync modes:**

| Mode | When used | What it downloads |
|------|-----------|-------------------|
| Backfill | First run, or after a reset | All historical documents |
| Incremental | Every subsequent sync | Only documents newer than the last known ID |

---

## 3. First-time setup

### Installation

1. Download the latest `TikiTakaPAYDWH-Setup-x64.exe` installer.
2. Double-click the installer and follow the prompts. Administrator rights are not required — it installs per-user to `%LOCALAPPDATA%\Programs\TikiTakaPAYDWH`.
3. A shortcut is added to your Start Menu under **Tiki-Taka PAY DWH** and to your Desktop.
4. Launch the application from the Start Menu shortcut. Your browser will open automatically.

### Onboarding wizard

The first time you open the application, a three-step setup wizard appears:

**Step 1 — Welcome.** Read the overview and click **Get started →**.

**Step 2 — API credentials.** Enter the Client ID and Client secret provided by your Tikitaka account manager. These credentials are saved in the Windows Credential Manager and never written to a plain-text file. Click **Test connection** to verify they work, then **Save & continue →**.

**Step 3 — Initial sync.** Click **Start sync** to begin downloading your transaction history. See the section below if you have a large number of documents.

### Large initial syncs

If your business has tens of thousands of documents, the first full download can take many minutes, and a laptop sleep or network interruption will stop it mid-way.

**The good news:** the application checkpoints its progress every 1 000 documents. If a sync is interrupted, the next click of **Sync now** automatically continues from where it stopped — it does not start over.

**Recommended workflow:**

1. Click **Sync now** in the sidebar. It downloads pages of documents and writes them as JSON files to your local disk. Progress is shown in the sidebar.
2. If the computer sleeps or the network drops, the download stops. Every file already written to disk is safe.
3. To see partial data in the dashboards immediately, without waiting for the full download to finish:
   - Go to **Diagnostics** (in the sidebar navigation).
   - Scroll to the **Raw data on disk** section.
   - Click **🔄 Rebuild warehouse from raw JSON**.
   - The warehouse is populated with whatever is already on disk. Dashboards will update with partial data.
4. Click **Sync now** again. It resumes automatically from the last checkpoint.
5. Repeat steps 3–4 if needed. The sidebar shows the current progress offset.

> **Tip for very large datasets:** Open a PowerShell window and run `python scripts/build_from_raw.py` while the backfill runs in the browser simultaneously. The two are safe to run at the same time — both use upserts, so no document is duplicated.

> **Tip to prevent sleep:** Open Windows **Settings → System → Power & sleep** and temporarily set both timeouts to **Never** while the initial sync runs.

---

## 4. The interface

### Navigation

The left sidebar contains all controls. Use the radio button list near the bottom to switch between pages:

- Revenue
- Products
- Stores & POS
- Heatmap
- VAT
- Z Reports
- Settings
- Diagnostics

### Global filters

The top of the sidebar contains filters that apply to every dashboard page simultaneously:

| Filter | What it does |
|--------|-------------|
| **From / To** | Date range. Defaults to the last 30 days. |
| **Stores** | Multi-select list of store numbers. Defaults to all. |
| **POS terminals** | Multi-select list of terminal IDs. Defaults to all. |

Change any filter and the active page recalculates immediately.

### Sync controls

- **Last synced** — timestamp of the last successful sync.
- **Sync now** button — runs an incremental sync (or a resuming backfill if one is in progress). A progress bar appears during the download.

---

## 5. Everyday features

### 5.1 Revenue

**What it shows:** Financial performance across all stores over the selected period.

| Metric | Meaning |
|--------|---------|
| Gross revenue | Sum of `doc_sum` for all sales transactions |
| Net revenue | Gross revenue minus total VAT collected |
| Transactions | Count of sales documents |
| Avg basket | Mean transaction value |

**Charts:** Daily revenue line chart, weekly revenue bar chart.

**Breakdown table:** Revenue by date and store. Exportable to CSV.

---

### 5.2 Products

**What it shows:** Which products and departments are driving revenue and volume.

- Toggle ranking between **Revenue** and **Quantity** sold.
- Choose Top 10, Top 20, or Top 50 products.
- **Revenue by department** bar chart.
- **Product search** — type any part of a product name or code; results update live.

Exportable to Excel.

---

### 5.3 Stores & POS

**What it shows:** Performance by physical location and hardware terminal.

- Revenue and transaction count by store.
- Revenue and transaction count by POS terminal.
- Operator (cashier) leaderboard.
- **Period comparison** — automatically compares the selected period against the immediately preceding period of equal length.

---

### 5.4 Heatmap — Peak Times

**What it shows:** When your business is busiest.

A day-of-week × hour-of-day heatmap. Darker cells = higher value. Toggle between transaction count and gross revenue. An hourly bar chart shows the aggregate pattern across all days.

---

### 5.5 VAT Summary

**What it shows:** VAT collected by rate, and a reconciliation check.

| Column | Meaning |
|--------|---------|
| VAT rate name | Label from the Tikitaka system (e.g. "PVN 21%") |
| Rate (%) | Numeric rate |
| Net amount (€) | Sales value excluding VAT |
| VAT amount (€) | VAT collected |
| Gross amount (€) | Net + VAT |
| Lines | Number of sale lines at this rate |

**Reconciliation:** Compares document-level totals against sale-line totals. A difference within €0.02 is highlighted green (✓); above €0.02 is highlighted red (⚠) and should be investigated before submitting a VAT return. Exportable to Excel.

---

### 5.6 Z Reports

**What it shows:** End-of-day Z-report close-outs as recorded by each POS terminal.

Each row is a single terminal close-out. Columns include date, store, terminal ID, operator, opening total, closing total, and cash movements. Use this page to reconcile daily cash-up figures with the POS printouts.

---

## 6. Keeping data up to date

### Manual sync

Click **Sync now** in the sidebar at any time. The sync fetches only documents that arrived after the last known watermark ID, so repeated syncs are fast (typically a few seconds).

### What happens during a sync

1. The app requests an OAuth2 access token using your stored credentials.
2. It calls the Tikitaka API, fetching only documents with an ID greater than the last watermark.
3. Each page of results is written as a JSON file to the raw data lake on disk **before any transformation begins**. The raw files are safe even if the sync is interrupted at any later stage.
4. Each page is also transformed into Parquet staging files.
5. After all pages are downloaded, staging files are loaded into the DuckDB warehouse using upserts (insert-or-replace by document ID).
6. Aggregate tables are rebuilt.
7. The **Last synced** timestamp updates.

### Resume after interruption

Backfill syncs checkpoint progress to disk every 1 000 documents. If a sync is interrupted — laptop sleep, network drop, closing the browser tab — the next **Sync now** click automatically resumes from the last checkpoint. You will see a message like:

> *Resuming backfill from API skip=14 000*

You never lose more than 1 000 documents worth of API calls. Any raw JSON files already written during the interrupted run are preserved and will be included in the next load.

### If a sync fails

The sidebar shows a red error state. The full traceback is in **Diagnostics → Log tail**. Common causes and fixes are in [Troubleshooting](#10-troubleshooting). After resolving the issue, click **Sync now** to retry — the resume checkpoint means you pick up where you left off.

---

## 7. Administration

### 7.1 Settings

| Setting | Description |
|---------|-------------|
| API base URL | The Tikitaka REST API endpoint. Leave as default unless told otherwise. |
| Client ID / Client secret | Your API credentials. Stored in Windows Credential Manager. |
| Data folder | Directory containing the database, raw lake, staging, and logs. |
| Sentry DSN | Optional crash reporting. Leave blank to disable. |
| Log level | `INFO` for normal use; `DEBUG` when investigating a problem. |

To change credentials: click **Change credentials**, fill in the new values, test the connection, and save. Changing credentials does not affect stored data.

To remove all credentials (triggers onboarding wizard on next launch): click **Clear credentials**.

### 7.2 Diagnostics

| Section | What it shows |
|---------|--------------|
| System info | App version, Python version, OS, data directory, warehouse file size |
| Sync state | Last synced timestamp, last seen document ID, resume checkpoint |
| API check | Live test of the API endpoint — HTTP status and response time |
| Log tail | Last 20 lines of `app.log` |
| **Raw data on disk** *(new in 0.2.0)* | File count, total records, unique document IDs, duplicate count, ID range |

**Raw data on disk — actions:**

- **Rebuild from raw** — reads all JSON files currently on disk, deduplicates by document ID, and loads the result into the warehouse using upserts. Makes no API calls. Safe to run at any time, including while a sync is in progress.
- **Update watermark** checkbox — only tick this if you are certain that all documents have been downloaded. Ticking it tells the application "the download is complete up to this ID" and the next incremental sync will not go back for older documents.

**Downloading diagnostics:** Click **Copy / download diagnostics** to save a plain-text snapshot (`tikitaka_diag.txt`). Attach this file when reporting a problem.

### 7.3 Command-line tools

Open a PowerShell window and navigate to the project root (or the installed `scripts/` folder). Use `uv run python <script>` when running from source, or `python <script>` from a terminal where the app's Python is on the path.

---

#### `reset_warehouse.py` — wipe the database

Deletes `warehouse.duckdb` and all staging Parquet files, then recreates the empty schema. **Raw JSON files are not deleted**, so you can rebuild from raw afterwards without any API calls.

```powershell
python scripts/reset_warehouse.py        # prompts for confirmation
python scripts/reset_warehouse.py --yes  # skip prompt (use in scripts)
```

---

#### `dev_sync.py` — headless sync

Runs a sync without launching the UI. Useful for scheduled tasks or servers without a display.

```powershell
python scripts/dev_sync.py                    # incremental (default)
python scripts/dev_sync.py --mode backfill    # full backfill from the start
```

---

#### `build_from_raw.py` — load on-disk data without API calls *(new in 0.2.0)*

Reads every raw JSON file already on disk, deduplicates by document ID, and loads the result into the warehouse. Does not contact the API. Safe to run multiple times.

```powershell
# Load all raw JSON into the warehouse
python scripts/build_from_raw.py

# Count files and duplicates without modifying the warehouse
python scripts/build_from_raw.py --audit-only

# Also advance the sync watermark after loading
# WARNING: only use this when you are sure ALL documents are on disk
python scripts/build_from_raw.py --set-watermark

# Override the data directory
python scripts/build_from_raw.py --data-dir "D:\TikiTakaData"

# Skip the confirmation prompt
python scripts/build_from_raw.py --yes
```

> ⚠️ **`--set-watermark` warning.** This flag tells the app "I have all documents up to this ID." If you use it when only a partial download is on disk, the app will never fetch the older documents that are missing. Only use this flag when you are certain the download is complete.

---

## 8. Upgrading to a new version

Upgrading is straightforward — just install the new `.exe`. You do not need to uninstall the old version first.

**Step by step:**

1. Download the new installer, e.g. `TikiTakaPAYDWH-Setup-x64.exe`.
2. If the application is open, close it. The installer will detect a running process and offer to close it automatically — but closing it yourself first is safer.
3. Run the installer and follow the prompts. It will overwrite the program files in `%LOCALAPPDATA%\Programs\TikiTakaPAYDWH`.
4. Launch the application normally after the installer finishes.

**Your data is completely safe:**

| Directory | Contents | Touched by installer? |
|-----------|----------|-----------------------|
| `%LOCALAPPDATA%\Programs\TikiTakaPAYDWH\` | Executable and Python libraries | ✅ Overwritten (this is the point) |
| `%LOCALAPPDATA%\TikiTakaPAYDWH\` | Database, raw files, credentials | ❌ Never touched |

- `warehouse.duckdb`, all raw JSON files, staging Parquet files, and application logs are in the data directory and are never modified by the installer.
- Credentials in Windows Credential Manager are also untouched.
- If the new version requires database schema changes (new columns, new tables), the migration runs automatically the first time the upgraded application starts. You will not notice anything — the app just starts normally.

After upgrading, the new version number appears in **Diagnostics → System info** and in Windows **Settings → Apps**.

---

## 9. Configuration reference

### Environment variables

All settings use the `TIKITAKA_` prefix and can be placed in a `.env` file in the working directory, or set as Windows user environment variables.

| Variable | Default | Description |
|----------|---------|-------------|
| `TIKITAKA_API_BASE_URL` | `https://api.manage.tikitaka.lv` | Base URL of the Tikitaka REST API |
| `TIKITAKA_APP_DATA_DIR` | Platform default (see below) | Directory for the warehouse, lake, and logs |
| `TIKITAKA_SENTRY_DSN` | *(unset)* | Sentry DSN for crash reporting; leave unset to disable |
| `TIKITAKA_LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Default data directories

| Platform | Default path |
|----------|-------------|
| Windows | `%LOCALAPPDATA%\TikiTakaPAYDWH` |
| macOS | `~/Library/Application Support/TikiTakaPAYDWH` |
| Linux | `~/.local/share/TikiTakaPAYDWH` |

### Data directory structure

```
<app_data_dir>/
├── warehouse.duckdb          ← DuckDB analytical database
├── lake/
│   ├── raw/                  ← Append-only raw JSON files from the API
│   │   └── dt=YYYY-MM-DD/    ← Partitioned by document date
│   └── staging/              ← Parquet files (intermediate transform output)
│       ├── documents/
│       ├── sale_lines/
│       └── payments/
└── logs/
    └── app.log               ← Rolling application log
```

---

## 10. Troubleshooting

### App opens but shows "No data yet"

You have not completed a sync. Click **Sync now** in the sidebar. If this is a fresh install, a full backfill will run automatically.

---

### First sync is very slow or keeps stopping

This is expected for large document histories. Use the resume workflow:

1. Let **Sync now** run as long as possible. Every 1 000 documents, progress is saved automatically.
2. If interrupted, go to **Diagnostics → Raw data on disk → Rebuild from raw** to load what is already on disk.
3. Click **Sync now** again — it resumes from the checkpoint, not from the beginning.
4. Repeat until the sync completes.

For the fastest results, run `python scripts/build_from_raw.py` from a PowerShell window while the UI sync runs simultaneously.

To prevent the laptop from sleeping during the sync: **Windows Settings → System → Power & sleep → set both timeouts to Never**.

---

### Sync fails with "Connection refused" or "Timeout"

- Check your internet connection.
- Open **Diagnostics → API check** — this tests the API endpoint directly and shows the HTTP status or error detail.
- If you are behind a corporate proxy or firewall, ensure outbound HTTPS (port 443) to `api.manage.tikitaka.lv` is allowed.

---

### Sync fails with "Invalid credentials (401)"

Your client ID or client secret has expired or changed. Go to **Settings**, enter the new values, test the connection, and save. Then click **Sync now**.

---

### Sync fails with an unexpected error

1. Go to **Diagnostics → Log tail**. Look for the most recent `ERROR` line.
2. Click **Copy / download diagnostics** to save a full report.
3. Send the `tikitaka_diag.txt` file to your support contact.

---

### Revenue figures look wrong after a sync

Run a warehouse rebuild from raw to ensure all data is consistently transformed:

```powershell
python scripts/reset_warehouse.py     # wipes only the DB, not raw JSON
python scripts/build_from_raw.py      # reloads from raw without API calls
```

If raw files are missing data, run **Sync now** afterwards to fetch the gaps.

---

### I need to re-download everything from scratch

```powershell
# Wipe the database and staging files (keeps raw JSON)
python scripts/reset_warehouse.py

# To also wipe raw JSON and force a full re-download:
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\TikiTakaPAYDWH\lake\raw"
```

Then click **Sync now** in the UI. A full backfill starts automatically.

---

### The app was moved to a new computer

1. On the old computer, copy `%LOCALAPPDATA%\TikiTakaPAYDWH` to external storage.
2. Install the app on the new computer using the standard installer.
3. Before the first launch, place the copied folder at `%LOCALAPPDATA%\TikiTakaPAYDWH` on the new machine.
4. Launch the app — the existing warehouse and raw files are detected automatically.
5. Re-enter your API credentials in **Settings** (they cannot be exported from Windows Credential Manager).

---

### Where are credentials stored?

Credentials are stored in **Windows Credential Manager** under the entry `TikiTakaPAYDWH`. They are never written to any file in the data or installation directories.

To view or delete them: **Control Panel → Credential Manager → Windows Credentials**, look for `TikiTakaPAYDWH`.
