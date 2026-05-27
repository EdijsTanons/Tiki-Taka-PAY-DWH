# Tiki-Taka PAY DWH — User Guide

## Contents

1. [What is Tiki-Taka PAY DWH?](#1-what-is-tikitaka-dwh)
2. [How it works](#2-how-it-works)
3. [First-time setup](#3-first-time-setup)
4. [The interface](#4-the-interface)
5. [Everyday features](#5-everyday-features)
   - [Revenue](#51-revenue)
   - [Products](#52-products)
   - [Stores & POS](#53-stores--pos)
   - [Heatmap — Peak Times](#54-heatmap--peak-times)
   - [VAT Summary](#55-vat-summary)
6. [Keeping data up to date](#6-keeping-data-up-to-date)
7. [Administration](#7-administration)
   - [Settings](#71-settings)
   - [Diagnostics](#72-diagnostics)
   - [Command-line tools](#73-command-line-tools)
8. [Configuration reference](#8-configuration-reference)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. What is Tiki-Taka PAY DWH?

Tiki-Taka PAY DWH is a desktop analytics application for Tikitaka point-of-sale clients. It downloads your fiscal document data from the Tikitaka cloud API and stores it **entirely on your own computer** — no third-party cloud service ever receives your sales data.

Once the initial sync is complete, all dashboards work fully offline. Internet access is only required when syncing new data from the API.

**What you can do with it:**

- Track gross and net revenue by day, week, store, and POS terminal.
- Analyse your best-selling products and departments.
- Compare operator (cashier) performance.
- Identify peak hours and days of the week.
- Produce a VAT summary with line-level reconciliation.
- Export any table to CSV or Excel for further analysis.

---

## 2. How it works

```
Tikitaka API  →  Raw JSON lake  →  Staging Parquet  →  DuckDB warehouse  →  Dashboards
```

1. **Sync** — The app calls the Tikitaka REST API using your OAuth credentials and downloads fiscal documents (sales, Z-reports, X-reports, etc.) as raw JSON files, stored under `lake/raw/` on your hard drive.

2. **Transform** — Each downloaded page is immediately converted into structured Parquet files (`lake/staging/`) covering three fact tables: documents, sale lines, and payments.

3. **Load** — After the sync finishes, all staging Parquet files are loaded into an embedded DuckDB database (`warehouse.duckdb`). The warehouse also maintains dimension tables (stores, POS terminals, operators, products, customers) and pre-built aggregate tables for fast dashboard queries.

4. **Dashboards** — The Streamlit-based UI reads directly from the local DuckDB file. All queries run in-process; there is no separate database server.

**Sync modes:**

| Mode | When used | What it downloads |
|------|-----------|-------------------|
| Backfill | First run (or after a reset) | All historical documents from the beginning |
| Incremental | Every subsequent sync | Only documents newer than the last known ID |

---

## 3. First-time setup

### Installation

Install the distributed package for your platform (Windows installer, macOS app bundle, or Linux AppImage) and launch it. Alternatively, if running from source:

```
python -m tikitaka_dwh
```

### Onboarding wizard

On the very first launch, Tiki-Taka PAY DWH shows a three-step setup wizard.

**Step 1 — Welcome**

Read the overview and click **Get started →**.

**Step 2 — API credentials**

Enter the **Client ID** and **Client secret** provided by your Tikitaka account manager.

> These credentials identify your account to the Tikitaka API. The application never stores your Tikitaka login password.

Click **Test connection**. The button is only enabled once both fields are filled. A successful test shows a green confirmation; a failure shows the error reason (for example, *Invalid credentials (401)*).

Once the test passes, click **Save & continue →**. Credentials are saved in the OS keychain (Windows Credential Manager, macOS Keychain, Linux Secret Service). On systems where a keychain is unavailable, an encrypted file is used as a fallback.

**Step 3 — Initial data sync**

Click **Start sync**. A progress bar tracks the download. Depending on your data volume this may take several minutes. When complete, the app redirects automatically to the Revenue dashboard.

---

## 4. The interface

### Navigation

The left sidebar contains all navigation controls. Use the **radio button list** at the bottom of the sidebar to switch between pages:

- Revenue
- Products
- Stores & POS
- Heatmap
- VAT
- Settings
- Diagnostics

### Global filters

The top of the sidebar contains filters that apply to every dashboard page:

| Filter | What it does |
|--------|-------------|
| **From / To** | Date range. Defaults to the last 30 days. |
| **Stores** | Multi-select list of store numbers. Defaults to all stores. |
| **POS terminals** | Multi-select list of POS IDs. Defaults to all terminals. |

Change any filter and the active page recalculates immediately.

### Sync controls

Above the filters you will find:

- **Last synced** timestamp — shows when data was last refreshed.
- **Sync now** button — runs an incremental sync in the sidebar. A progress bar appears during the download. When finished, all charts update automatically.

---

## 5. Everyday features

### 5.1 Revenue

**What it shows:** Financial performance of your stores over the selected period.

**Top metrics row**

| Metric | Meaning |
|--------|---------|
| Gross revenue | Sum of `doc_sum` for all sales transactions |
| Net revenue | Gross revenue minus the total VAT collected |
| Transactions | Number of sales documents |
| Avg basket | Mean transaction value |

**Daily revenue chart** — Line chart of gross revenue by calendar date. Use this to spot day-to-day patterns and outliers.

**Weekly revenue chart** — Bar chart aggregated by ISO week start (Monday). Use this to compare weeks at a glance.

**Daily breakdown table** — Tabular view grouped by date and store number. Columns: Date, Store, Gross (€), Transactions.

**Export:** Click **Export CSV** below the table to download the breakdown.

---

### 5.2 Products

**What it shows:** Which products and departments are driving revenue and volume.

**Top N products**

- Toggle between ranking by **Revenue** or **Quantity** using the radio buttons.
- Choose how many products to show: **Top 10**, **Top 20**, or **Top 50**.
- A bar chart shows the ranking visually.
- The table below lists: Product code, Product name, Department, Quantity sold, Revenue (€), Line count.

**Revenue by department** — Bar chart showing the share of revenue contributed by each product department. Useful for understanding your category mix.

**Product search** — Type any part of a product name or product code into the search box. Results update in real time and show: Code, Product name, Department, Quantity, Revenue (€), Average price (€), Line count.

**Export:** Click **Export Excel** below the search results to download the filtered product list.

---

### 5.3 Stores & POS

**What it shows:** Performance broken down by physical location and hardware terminal.

**Revenue by store** — Bar chart and table: Store number, Gross revenue (€), Transactions, Avg basket (€). Sorted by gross revenue descending.

**Revenue by POS terminal** — Bar chart and table: POS ID, Device serial number, Store, Gross revenue (€), Transactions. A caption shows the combined total across all terminals.

**Operator leaderboard** — Table of cashiers/operators ranked by gross revenue: Operator ID, Operator name, Gross revenue (€), Transactions, Avg basket (€).

**Period comparison** — Automatically compares the selected period against the immediately preceding period of equal length.

For example, if your filter covers 1–14 May, the comparison period is 17–30 April. The metrics displayed are:

- Gross revenue (current vs prior)
- Transaction count (current vs prior)

This makes it easy to assess whether performance has improved or declined.

---

### 5.4 Heatmap — Peak Times

**What it shows:** At which hours and days your business is busiest.

The heatmap is a table where rows are **hours of the day** (00:00–23:00) and columns are **days of the week** (Monday–Sunday). Each cell is coloured on a yellow-orange-red gradient: the darker the cell, the higher the value.

Toggle between:

- **Transactions** — count of sales per slot
- **Revenue (€)** — gross revenue per slot

**Hourly bar chart** — Shows the aggregate transaction volume by hour across all days and stores in the selected period. Use this to identify opening/closing patterns and lunch-hour peaks.

---

### 5.5 VAT Summary

**What it shows:** VAT collected, broken down by tax rate, and a reconciliation check.

**VAT by rate table** — One row per VAT rate name:

| Column | Meaning |
|--------|---------|
| VAT rate name | Label from the Tikitaka system (e.g. "PVN 21%") |
| Rate (%) | Numeric rate |
| Net amount (€) | Sales value excluding VAT |
| VAT amount (€) | VAT collected |
| Gross amount (€) | Net + VAT |
| Lines | Number of sale lines at this rate |

A **Totals** row is appended at the bottom. Export the table with **Export Excel**.

**VAT reconciliation** — Compares two independent totals:

- The `doc_sum` field on each document (the amount the customer actually paid)
- The sum of `total_sum` across all sale lines

Both figures should match within €0.02 (rounding tolerance). If the difference is within tolerance the row is highlighted green with a ✓ label. If it exceeds tolerance, it is highlighted red with a ⚠ warning — this warrants investigation before submitting VAT returns.

---

## 6. Keeping data up to date

### Manual sync

Click **Sync now** in the sidebar at any time. The sync runs incrementally — it fetches only the documents that arrived after the last known document ID — so repeated syncs are fast.

### What happens during a sync

1. New raw JSON pages are appended to `lake/raw/`.
2. Each page is immediately transformed and written to `lake/staging/` as Parquet files.
3. After the download completes, staging Parquet is loaded into `warehouse.duckdb`.
4. All aggregate tables are rebuilt.
5. The sidebar shows the updated **Last synced** timestamp.

### If a sync fails

The error message appears in the sidebar. The warehouse is not modified — the failed sync is rolled back entirely. Check the **Diagnostics** page for the full error trace from the log file.

---

## 7. Administration

### 7.1 Settings

Navigate to **Settings** in the sidebar.

#### API credentials

| Action | How |
|--------|-----|
| View the stored Client ID | Shown at the top of the section |
| Change credentials | Click **Change credentials**, fill in the new Client ID and Client secret, then **Save credentials** |
| Remove credentials | Click **Clear credentials** — this removes all stored credentials and returns to the onboarding wizard on the next launch |

> Changing or clearing credentials does not delete the local data. The warehouse and raw files are preserved.

#### Data folder

Displays the full path of the application data directory. This directory contains:

```
<app_data_dir>/
├── warehouse.duckdb       ← DuckDB analytical database
├── lake/
│   ├── raw/               ← Append-only raw JSON from the API
│   └── staging/           ← Parquet files (intermediate transform output)
└── logs/
    └── app.log            ← Rolling application log
```

To move data to a different drive or directory, set the `TIKITAKA_APP_DATA_DIR` environment variable before launching the app (see [Configuration reference](#8-configuration-reference)).

#### Crash reporting (Sentry)

The app can optionally send anonymised error reports to a Sentry project. **No customer data or PII is ever included.** Crash reporting is disabled by default.

To enable, enter your Sentry DSN in the field provided and click **Enable crash reporting**. To disable, click **Disable crash reporting** (which instructs you to unset the `TIKITAKA_SENTRY_DSN` environment variable).

---

### 7.2 Diagnostics

Navigate to **Diagnostics** in the sidebar.

The diagnostics panel provides a single-screen health check:

| Section | Information shown |
|---------|------------------|
| System information | App version, Python version, OS platform, data directory path, warehouse file size |
| Sync state | Timestamp of last completed sync, ID of the last-seen document |
| API reachability | Whether the Tikitaka API endpoint is reachable, HTTP status or error detail |
| Recent log entries | Last 20 lines of `app.log` |

**Downloading diagnostics** — Click **Copy / download diagnostics** to save all the above information as a plain-text file (`tikitaka_diag.txt`). Attach this file when reporting a problem to your support contact.

---

### 7.3 Command-line tools

These scripts are intended for IT staff and advanced users. Run them from the project directory with `python -m uv run python <script>` when running from source.

#### Reset the warehouse

```
python scripts/reset_warehouse.py
```

Deletes `warehouse.duckdb`, `lake/raw/`, and `lake/staging/` so you can start a clean backfill. **Credentials are not affected.**

You will be asked to type `yes` to confirm before anything is deleted. To skip the prompt (for example, in a script):

```
python scripts/reset_warehouse.py --yes
```

After a reset, run a backfill by clicking **Sync now** in the UI (which will automatically fall back to a full backfill because no watermark exists), or use the dev sync CLI below.

#### Dev sync CLI

```
python scripts/dev_sync.py --mode backfill
python scripts/dev_sync.py --mode incremental
```

Runs a sync without launching the UI. Useful for scheduled jobs, server deployments, or debugging. Progress is printed to the console. Credentials must already be stored (from the onboarding UI) or supplied via environment variables:

```
TIKITAKA_CLIENT_ID=your_id TIKITAKA_CLIENT_SECRET=your_secret python scripts/dev_sync.py
```

---

## 8. Configuration reference

All settings are controlled by environment variables with the `TIKITAKA_` prefix. You can also place them in a `.env` file in the working directory.

| Variable | Default | Description |
|----------|---------|-------------|
| `TIKITAKA_API_BASE_URL` | `https://api.manage.tikitaka.lv` | Base URL of the Tikitaka REST API |
| `TIKITAKA_APP_DATA_DIR` | Platform user-data folder (`TikiTakaPAYDWH`) | Directory for the warehouse, lake, and logs |
| `TIKITAKA_SENTRY_DSN` | *(unset)* | Sentry DSN for crash reporting; leave unset to disable |
| `TIKITAKA_LOG_LEVEL` | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `TIKITAKA_CLIENT_ID` | *(unset)* | API client ID; overrides the keychain-stored value |
| `TIKITAKA_CLIENT_SECRET` | *(unset)* | API client secret; overrides the keychain-stored value |

**Default data directory by platform:**

| Platform | Default path |
|----------|-------------|
| Windows | `%LOCALAPPDATA%\TikiTakaPAYDWH` |
| macOS | `~/Library/Application Support/TikiTakaPAYDWH` |
| Linux | `~/.local/share/TikiTakaPAYDWH` |

---

## 9. Troubleshooting

### The app opens but shows "No data yet"

You have not completed a sync. Click **Sync now** in the sidebar. If this is the first run and onboarding was somehow skipped, navigate to **Settings** and verify that credentials are stored.

### Sync fails with "Connection refused" or "Timeout"

Check your internet connection. Open the **Diagnostics** page — the API reachability row will confirm whether `api.manage.tikitaka.lv` is reachable. Also check whether a corporate firewall or proxy is blocking outbound HTTPS.

### Sync fails with "Invalid credentials (401)"

Your Client ID or Client secret has changed or expired. Go to **Settings → Change credentials**, enter the new values, test the connection, and save.

### Sync fails with an unexpected error

1. Open **Diagnostics** and check the recent log entries for a Python traceback.
2. Click **Copy / download diagnostics** and attach the file to your support request.

### Revenue figures look wrong after a sync

Check the **VAT Summary → VAT reconciliation** row. A red warning (difference > €0.02) indicates a mismatch between document-level totals and sale-line totals, which often points to a data quality issue on the API side. Note the document ID range shown in **Diagnostics → Last seen ID** and report it to your Tikitaka account manager.

### I need to re-download all data from scratch

Run the reset script:

```
python scripts/reset_warehouse.py
```

Then click **Sync now** in the UI. A full backfill will start automatically.

### The app was moved to a new computer

1. Install the app on the new machine.
2. Complete onboarding with the same credentials.
3. Click **Sync now** to re-download all data.

Alternatively, copy the entire `app_data_dir` folder from the old machine to the same location on the new machine. The warehouse file is self-contained and portable.

### Where are my credentials stored?

On Windows: **Windows Credential Manager** under the entry `tikitaka_dwh`. On macOS: **Keychain Access** under the same name. On Linux: **GNOME Keyring / KWallet** (whichever is the active Secret Service provider). On headless systems with no keychain, credentials are stored in an AES-256 Fernet-encrypted file inside the app data directory.

To remove credentials permanently, use **Settings → Clear credentials** or delete the entry directly from the OS keychain manager.
