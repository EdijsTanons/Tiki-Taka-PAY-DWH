"""Reset the local warehouse and raw data lake.

Usage:
    python -m tikitaka_dwh.scripts.reset_warehouse [--keep-credentials]

WARNING: This deletes all synced data. Use when you want a clean re-backfill.
"""

from __future__ import annotations

import argparse
import shutil
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete the local warehouse and raw/staging lake. "
                    "Does NOT delete credentials."
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Skip the confirmation prompt."
    )
    args = parser.parse_args()

    from tikitaka_dwh.config import get_settings

    settings = get_settings()
    app_dir = settings.app_data_dir
    db_path = app_dir / "warehouse.duckdb"
    raw_dir = app_dir / "lake" / "raw"
    staging_dir = app_dir / "lake" / "staging"

    print("This will delete:")
    print(f"  Warehouse DB:  {db_path}")
    print(f"  Raw lake:      {raw_dir}")
    print(f"  Staging lake:  {staging_dir}")
    print()

    if not args.yes:
        answer = input("Type 'yes' to confirm: ").strip().lower()
        if answer != "yes":
            print("Aborted.")
            sys.exit(0)

    if db_path.exists():
        db_path.unlink()
        wal = db_path.with_suffix(".duckdb.wal")
        if wal.exists():
            wal.unlink()
        print(f"Deleted: {db_path}")

    for d in (raw_dir, staging_dir):
        if d.exists():
            shutil.rmtree(d)
            print(f"Deleted: {d}")

    print("Reset complete. Run a backfill to re-populate.")


if __name__ == "__main__":
    main()
