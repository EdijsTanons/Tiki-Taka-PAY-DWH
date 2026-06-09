"""build_from_raw.py — load whatever raw JSON is on disk into the warehouse.

Run this from a terminal (PowerShell / cmd) instead of the Streamlit UI when
doing a large first-time sync that keeps getting interrupted by sleep.

Workflow
--------
1.  Let the Streamlit UI start the backfill — it writes raw JSON pages as it
    goes.  When the computer sleeps the sync stops, but every file written so
    far is safe on disk.
2.  Open a terminal and run this script to load everything that landed on disk:

        python scripts/build_from_raw.py

3.  Open the UI — you will already see partial data.
4.  Click "Sync now" again (or leave the backfill running) to fetch the rest.
    The backfill will resume from its last checkpoint automatically.

Flags
-----
--audit-only      Print deduplication stats but do not write to the warehouse.
--set-watermark   After loading, advance the watermark to the highest doc ID
                  in the raw files.  Only use this when you are certain ALL
                  documents have been downloaded; otherwise the next incremental
                  sync will miss older documents that haven't been fetched yet.
--data-dir PATH   Override the app data directory (default: platform default).
--yes             Skip the confirmation prompt.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _app_data_dir() -> Path:
    try:
        from tikitaka_dwh.config import get_settings
        return get_settings().app_data_dir
    except Exception as exc:
        print(f"Warning: could not read app settings ({exc}); using current directory.")
        return Path(".")


def _print_stats(stats: dict) -> None:  # type: ignore[type-arg]
    print()
    print("  Raw files found   :", stats["files"])
    if stats.get("failed_files"):
        print("  Unreadable files  :", stats["failed_files"], " ← skipped, see app.log")
    print("  Total doc records :", stats["total_docs"])
    print("  Unique doc IDs    :", stats["unique_ids"])
    print("  Duplicate records :", stats["duplicate_docs"])
    if stats.get("min_id") is not None:
        print(f"  ID range          : {stats['min_id']} – {stats['max_id']}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load raw JSON files into the warehouse.")
    parser.add_argument("--audit-only", action="store_true",
                        help="Show stats only, do not modify the warehouse.")
    parser.add_argument("--set-watermark", action="store_true",
                        help="Advance the watermark to max doc ID in raw files "
                             "(only safe when all docs are downloaded).")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="Override the app data directory.")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the confirmation prompt.")
    args = parser.parse_args()

    data_dir = args.data_dir or _app_data_dir()
    raw_dir = data_dir / "lake" / "raw"
    db_path = data_dir / "warehouse.duckdb"

    print(f"\nData dir : {data_dir}")
    print(f"Raw dir  : {raw_dir}")
    print(f"Database : {db_path}")

    if not raw_dir.exists() or not any(raw_dir.rglob("*.json")):
        print("\nNo raw JSON files found — nothing to do.")
        sys.exit(0)

    # Audit first — always free
    print("\nScanning raw files …")
    from tikitaka_dwh.warehouse.db import audit_raw
    stats = audit_raw(raw_dir)
    _print_stats(stats)

    if args.audit_only:
        sys.exit(0)

    if not db_path.exists():
        print("Warehouse database does not exist yet — initialising …")
        from tikitaka_dwh.warehouse.db import initialize_warehouse
        initialize_warehouse(db_path)

    if not args.yes:
        answer = input(
            f"Load {stats['unique_ids']:,} unique documents into warehouse? [y/N] "
        ).strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    watermark = None
    if args.set_watermark:
        from tikitaka_dwh.sync.watermark import WatermarkStore
        watermark = WatermarkStore(db_path)

    print("Loading …")
    from tikitaka_dwh.warehouse.db import rebuild_from_raw
    result = rebuild_from_raw(
        db_path=db_path,
        raw_dir=raw_dir,
        watermark=watermark,
        set_watermark=args.set_watermark,
    )

    print(f"\n✓  Done — {result['warehouse_rows']:,} documents loaded.")
    if result.get("failed_files"):
        print(f"   WARNING: {result['failed_files']} raw file(s) could not be read — the")
        print("   warehouse may be missing documents (see app.log).")
    if args.set_watermark and result.get("failed_files"):
        print("   Watermark NOT updated because of the unreadable files — fix or")
        print("   delete them and re-run with --set-watermark.")
    elif args.set_watermark and result["max_id"] is not None:
        print(f"   Watermark set to max_id={result['max_id']}")
    else:
        print("   Watermark NOT updated — the backfill can still resume and")
        print("   fetch remaining documents.  Re-run with --set-watermark only")
        print("   after the backfill completes fully.")
    print()


if __name__ == "__main__":
    main()
