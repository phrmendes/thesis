import sys
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from .data import build, fetch

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})
data = typer.Typer(name="data", help="Data pipeline commands")
app.add_typer(data)


@app.callback()
def set_verbose(verbose: Annotated[int, typer.Option("-v", "--verbose", count=True)] = 0) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level={0: "WARNING", 1: "INFO", 2: "DEBUG", 3: "TRACE"}[min(verbose, 3)],
        format="<level>[{level}]</level> {message}",
    )


@data.command(name="fetch", help="Download CS:GO price snapshots from csgotrader.app")
def fetch_cmd(
    start: Annotated[str, typer.Option("--start")] = "2020-12-31",
    end: Annotated[str, typer.Option("--end")] = "2023-10-01",
    data_dir: Annotated[str, typer.Option("--data-dir")] = "data",
    concurrency: Annotated[int, typer.Option("--concurrency", "-c")] = 10,
) -> None:
    fetch(date.fromisoformat(start), date.fromisoformat(end), Path(data_dir), concurrency)


@data.command(name="build", help="Build a sorted DuckDB database from Parquet files")
def build_cmd(
    data_dir: Annotated[str, typer.Option("--data-dir")] = "data",
    db_path: Annotated[str, typer.Option("--db-path")] = "data/csgo.duckdb",
    headroom: Annotated[int, typer.Option("--headroom")] = 3,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    build(Path(data_dir), Path(db_path), headroom, force=force)
