from asyncio import Runner, Semaphore, as_completed, to_thread
from collections import Counter
from contextlib import suppress
from datetime import date, timedelta
from enum import Enum, auto
from gzip import BadGzipFile, decompress
from http import HTTPStatus
from pathlib import Path
from string import Template
from typing import TypedDict, cast

import orjson
import polars as pl
from duckdb import connect
from httpx import AsyncClient, HTTPStatusError, NetworkError, Response, TimeoutException, get
from pydantic import TypeAdapter
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from typer import progressbar
from uvloop import new_event_loop

from .constants import BASE_URL, ITEMS_URL, SQL_DIR
from .models import ItemData, ItemPrices


class FetchStatus(Enum):
    FETCHED = auto()
    CACHED = auto()
    GAP = auto()
    FAILED = auto()


class PriceRow(TypedDict):
    date: date
    item_hash_name: str
    steam_price: float | None
    buff163_price: float | None
    csgotrader_price: float | None


@retry(
    retry=retry_if_exception_type((HTTPStatusError, NetworkError, TimeoutException)),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
def fetch_items(language: str, output: Path) -> Path:
    """Download static item metadata from the CSGO-API repository."""
    response = get(ITEMS_URL.format(language=language), timeout=30)

    if response.status_code == HTTPStatus.TOO_MANY_REQUESTS or response.is_server_error:
        response.raise_for_status()

    items = TypeAdapter(dict[str, ItemData]).validate_json(response.content, strict=False)
    records = [item.model_dump(mode="json") for item in items.values()]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(orjson.dumps(records))
    return output


def has_item_metadata(db_path: Path) -> bool:
    """Return whether a database already contains item metadata."""
    if not db_path.exists():
        return False

    query = Template((SQL_DIR / "has_item_metadata.sql").read_text()).substitute()

    with connect(str(db_path), read_only=True) as conn:
        return cast(bool, conn.sql(query).pl().item())


@retry(
    retry=retry_if_exception_type((HTTPStatusError, NetworkError, TimeoutException)),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def request_snapshot(client: AsyncClient, url: str, sem: Semaphore) -> Response:
    async with sem:
        response = await client.get(url)

        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS or response.is_server_error:
            response.raise_for_status()

        return response


def extract_prices(name: str, item: ItemPrices, day: date) -> PriceRow:
    """Flatten a validated ItemPrices into a single PriceRow."""
    return {
        "date": day,
        "item_hash_name": name,
        "steam_price": item.steam.last_30d if item.steam else None,
        "buff163_price": (item.buff163.starting_at.price if item.buff163 and item.buff163.starting_at else None),
        "csgotrader_price": item.csgotrader.price if item.csgotrader else None,
    }


def process_snapshot(body: bytes, day: date, path: Path) -> FetchStatus:
    """Validate and persist one downloaded snapshot."""
    with suppress(BadGzipFile):
        body = decompress(body)

    raw = TypeAdapter(dict[str, ItemPrices]).validate_json(body, strict=False)

    if not raw:
        return FetchStatus.GAP

    rows = [extract_prices(name, item, day) for name, item in raw.items()]
    pl.DataFrame(rows).write_parquet(path)
    return FetchStatus.FETCHED


async def fetch_day(
    client: AsyncClient,
    day: date,
    sem: Semaphore,
    data_dir: Path,
    *,
    force: bool,
) -> FetchStatus:
    """Download and persist one daily snapshot from csgotrader.app."""
    path = data_dir / f"{day}.parquet"

    if path.exists() and not force:
        return FetchStatus.CACHED

    url = f"{BASE_URL}/{day:%Y/%m/%d}/prices_v6.json"

    try:
        resp = await request_snapshot(client, url, sem)
    except HTTPStatusError, NetworkError, TimeoutException:
        return FetchStatus.FAILED

    if resp.status_code in {
        HTTPStatus.MOVED_PERMANENTLY,
        HTTPStatus.FOUND,
        HTTPStatus.NOT_FOUND,
    }:
        return FetchStatus.GAP

    resp.raise_for_status()
    return await to_thread(process_snapshot, resp.content, day, path)


def fetch(
    start: date,
    end: date,
    data_dir: Path,
    concurrency: int,
    *,
    force: bool = False,
) -> dict[str, int]:
    """Fetch all available daily snapshots, retrying transient failures.

    Returns {"fetched": N, "skipped": N, "failed": N}.
    """
    data_dir.mkdir(exist_ok=True)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    sem = Semaphore(concurrency)

    async def run() -> dict[str, int]:
        async with AsyncClient() as client:
            tasks = [fetch_day(client, day, sem, data_dir, force=force) for day in days]
            counts: Counter[FetchStatus] = Counter()

            with progressbar(as_completed(tasks), length=len(tasks)) as progress:
                for task in progress:
                    counts[await task] += 1

        return {
            "fetched": counts[FetchStatus.FETCHED],
            "skipped": counts[FetchStatus.CACHED] + counts[FetchStatus.GAP],
            "failed": counts[FetchStatus.FAILED],
        }

    with Runner(loop_factory=new_event_loop) as runner:
        return runner.run(run())
