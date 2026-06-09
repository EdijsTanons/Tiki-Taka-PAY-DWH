"""CLI for testing sync without the UI.

Usage:
    python -m tikitaka_dwh.scripts.dev_sync --mode backfill
    python -m tikitaka_dwh.scripts.dev_sync --mode incremental
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


async def _run(mode: str) -> None:
    import httpx

    from tikitaka_dwh.api.client import TikitakaClient
    from tikitaka_dwh.auth import TokenProvider, load_credentials
    from tikitaka_dwh.config import ensure_app_dirs, get_settings
    from tikitaka_dwh.observability.logging import configure_logging
    from tikitaka_dwh.sync.engine import SyncEngine
    from tikitaka_dwh.sync.watermark import WatermarkStore
    from tikitaka_dwh.warehouse.db import initialize_warehouse, load_staging_to_warehouse

    ensure_app_dirs()
    settings = get_settings()
    configure_logging(settings.app_data_dir / "logs", settings.log_level)

    creds = load_credentials()
    if not creds:
        print("No credentials found. Run the onboarding UI first or set TIKITAKA_CLIENT_ID/SECRET env vars.", file=sys.stderr)
        sys.exit(1)

    client_id, client_secret = creds
    staging_dir = settings.app_data_dir / "lake" / "staging"

    async with httpx.AsyncClient() as http:
        provider = TokenProvider(
            username_provider=lambda: client_id,
            password_provider=lambda: client_secret,
            base_url=settings.api_base_url,
            http_client=http,
        )
        client = TikitakaClient(settings.api_base_url, provider, http)
        watermark = WatermarkStore(settings.app_data_dir / "warehouse.duckdb")
        initialize_warehouse(settings.app_data_dir / "warehouse.duckdb")

        engine = SyncEngine(
            client=client,
            raw_dir=settings.app_data_dir / "lake" / "raw",
            watermark=watermark,
            staging_dir=staging_dir,
        )

        def progress(done: int, total: int | None) -> None:
            total_str = str(total) if total else "?"
            print(f"\r  {done}/{total_str} documents synced …", end="", flush=True)

        if mode == "backfill":
            count = await engine.run_backfill(progress=progress)
        else:
            count = await engine.run_incremental(progress=progress)

        print(f"\nDone. {count} documents {'fetched (backfill)' if mode == 'backfill' else 'new (incremental)'}.")

    load_staging_to_warehouse(settings.app_data_dir / "warehouse.duckdb", staging_dir)
    print("Warehouse updated.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dev sync CLI")
    parser.add_argument("--mode", choices=["backfill", "incremental"], default="incremental")
    args = parser.parse_args()
    asyncio.run(_run(args.mode))


if __name__ == "__main__":
    main()
