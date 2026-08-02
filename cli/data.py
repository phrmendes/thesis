import asyncio
from asyncio import Semaphore
from datetime import date, timedelta
from gzip import BadGzipFile, decompress
from http import HTTPStatus
from os import cpu_count
from pathlib import Path
from string import Template
from typing import TypedDict, cast

import polars as pl
from duckdb import connect
from httpx import AsyncClient
from loguru import logger
from pydantic import TypeAdapter
from uvloop import new_event_loop

from cli.models import BuffStartingAt, ItemPrices

BASE_URL = "https://prices.csgotrader.app"
SQL_DIR = Path(__file__).resolve().parent / "sql"


class PriceRow(TypedDict):
    date: date
    item_hash_name: str
    source_data: dict[str, object]
    steam_price: float | None
    buff163_price: float | None
    csgotrader_price: float | None


def extract_prices(name: str, item: ItemPrices, day: date) -> PriceRow:
    """Flatten a validated ItemPrices into a single PriceRow."""
    return {
        "date": day,
        "item_hash_name": name,
        "source_data": item.model_dump(),
        "steam_price": item.steam.last_30d if item.steam else None,
        "buff163_price": (
            item.buff163.starting_at.price
            if item.buff163 and isinstance(item.buff163.starting_at, BuffStartingAt)
            else None
        ),
        "csgotrader_price": item.csgotrader.price if item.csgotrader else None,
    }


async def fetch_day(client: AsyncClient, day: date, sem: Semaphore, data_dir: Path) -> None:
    """Download and persist one daily snapshot from csgotrader.app."""
    path = data_dir / f"{day}.parquet"

    if path.exists():
        logger.debug("Skipping {}: already fetched", day)
        return

    url = f"{BASE_URL}/{day:%Y/%m/%d}/prices_v6.json"

    async with sem:
        logger.info("Fetching {}", day)
        resp = await client.get(url)
        if resp.status_code in (HTTPStatus.MOVED_PERMANENTLY, HTTPStatus.FOUND, HTTPStatus.NOT_FOUND):
            logger.warning("Skipping {}: no data (HTTP {})", day, resp.status_code)
            return
        resp.raise_for_status()

    try:
        body = decompress(resp.content)
    except BadGzipFile:
        body = resp.content

    raw = TypeAdapter(dict[str, ItemPrices]).validate_json(body, strict=False)
    if not raw:
        logger.warning("Skipping {}: empty response", day)
        return

    logger.success("{}: {} items decoded", day, len(raw))
    rows = [extract_prices(name, item, day) for name, item in raw.items()]
    pl.DataFrame(rows).write_parquet(path)
    logger.success("{}: wrote {} rows to {}", day, len(rows), path)


def fetch(start: date, end: date, data_dir: Path, concurrency: int) -> None:
    """Fetch all available daily snapshots, skipping already-downloaded days."""
    logger.info("Starting fetch: {} -> {}", start, end)
    data_dir.mkdir(exist_ok=True)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    sem = Semaphore(concurrency)

    async def run() -> None:
        async with AsyncClient() as client:
            await asyncio.gather(*[fetch_day(client, day, sem, data_dir) for day in days])

    with asyncio.Runner(loop_factory=new_event_loop) as runner:
        runner.run(run())

    logger.success("Fetch complete")


def build(data_dir: Path, db_path: Path, headroom: int, *, force: bool = False) -> None:
    """Build a sorted DuckDB database from the raw Parquet files."""
    if db_path.exists() and not force:
        logger.warning("{} already exists, use --force to rebuild", db_path)
        return

    logger.info("Building {} from {}/*.parquet", db_path, data_dir)

    cpu = cpu_count() or 1
    threads = max(1, cpu - headroom)
    sql_kwargs = {"data_dir": str(data_dir)}
    build_sql = Template((SQL_DIR / "build.sql").read_text()).substitute(**sql_kwargs)
    count_parquet = Template((SQL_DIR / "count_parquet.sql").read_text()).substitute(**sql_kwargs)
    count_prices = (SQL_DIR / "count_prices.sql").read_text()

    with connect(str(db_path)) as conn:
        conn.execute(f"SET threads = {threads}")

        expected = cast(int, conn.sql(count_parquet).pl().item())
        logger.info("Parquet row count: {}", f"{expected:,}")

        conn.execute(build_sql)

        actual = cast(int, conn.sql(count_prices).pl().item())
        if actual != expected:
            logger.error("Row mismatch: expected {}, got {}", f"{expected:,}", f"{actual:,}")
            return

        logger.success("Build complete: {} rows", f"{actual:,}")

    for f in data_dir.glob("*.parquet"):
        f.unlink()

    logger.info("Cleaned up {}/*.parquet", data_dir)
