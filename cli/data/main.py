from datetime import date
from pathlib import Path
from typing import Annotated

from typer import Exit, Option, Typer, secho

from .build import build
from .clear import clear
from .constants import (
    DEFAULT_CONCURRENCY,
    DEFAULT_DATA_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_END,
    DEFAULT_HEADROOM,
    DEFAULT_ITEMS_PATH,
    DEFAULT_LANGUAGE,
    DEFAULT_START,
)
from .fetch import fetch, fetch_items, has_item_metadata
from .join import join
from .migrate_schemas import migrate_schemas

app = Typer(name="data", help="Data pipeline commands")


@app.command(name="fetch", help="Download CS:GO prices and item metadata")
def fetch_cmd(
    start: Annotated[str, Option("--start")] = DEFAULT_START,
    end: Annotated[str, Option("--end")] = DEFAULT_END,
    data_dir: Annotated[str, Option("--data-dir")] = DEFAULT_DATA_DIR,
    concurrency: Annotated[int, Option("--concurrency", "-c")] = DEFAULT_CONCURRENCY,
    *,
    force: Annotated[bool, Option("--force", "-f")] = False,
) -> None:
    database = Path(DEFAULT_DB_PATH)
    if database.exists() and not force:
        secho("Skipped price snapshots: database exists; use --force to refresh.", fg="yellow")
    else:
        result = fetch(
            date.fromisoformat(start),
            date.fromisoformat(end),
            Path(data_dir),
            concurrency,
            force=force,
        )
        secho(
            f"Fetched {result['fetched']}, skipped {result['skipped']}, failed {result['failed']}",
            fg="green",
        )

    items_path = Path(DEFAULT_ITEMS_PATH)

    if force or not has_item_metadata(database):
        path = fetch_items(DEFAULT_LANGUAGE, items_path)
        secho(f"Written {path}", fg="green")
        return

    secho("Skipped item metadata: items.json and database metadata exist.", fg="yellow")


@app.command(name="clear", help="Build returns with weekly metrics and outlier removal")
def clear_cmd() -> None:
    rows = clear()
    secho(f"Built returns with {rows:,} rows", fg="green")


@app.command(name="migrate-schemas", help="Move tables into raw, cleaned, and strategy schemas")
def migrate_schemas_cmd() -> None:
    migrated = migrate_schemas()
    message = "Migrated database schemas" if migrated else "Database schemas already migrated"
    secho(message, fg="green")


@app.command(name="join", help="Join prices with rarity and remove the source tables")
def join_cmd(
    db_path: Annotated[str, Option("--db-path")] = DEFAULT_DB_PATH,
) -> None:
    rows = join(Path(db_path))
    secho(f"Joined {rows:,} rows into prices", fg="green")


@app.command(name="build", help="Build one DuckDB database with prices and rarity data")
def build_cmd(
    data_dir: Annotated[str, Option("--data-dir")] = DEFAULT_DATA_DIR,
    db_path: Annotated[str, Option("--db-path")] = DEFAULT_DB_PATH,
    items_path: Annotated[str, Option("--items-path")] = DEFAULT_ITEMS_PATH,
    headroom: Annotated[int, Option("--headroom")] = DEFAULT_HEADROOM,
    *,
    force: Annotated[bool, Option("--force", "-f")] = False,
) -> None:
    try:
        result = build(Path(data_dir), Path(db_path), headroom, Path(items_path), force=force)
    except FileExistsError as err:
        secho(str(err), fg="yellow")
        raise Exit(1) from None

    secho(f"Built {result['rows']:,} rows", fg="green")
