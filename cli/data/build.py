from os import cpu_count
from pathlib import Path
from string import Template
from typing import cast

from duckdb import connect

from .constants import DEFAULT_ITEMS_PATH, SQL_DIR


def build(
    data_dir: Path,
    db_path: Path,
    headroom: int,
    items_path: Path | None = None,
    *,
    force: bool = False,
) -> dict[str, int]:
    """Build prices and item metadata tables in one DuckDB database.

    Returns {"rows": N}. Raises FileExistsError if db exists and force=False.
    Raises ValueError on row count mismatch.
    """
    if db_path.exists() and not force:
        raise FileExistsError(db_path)

    cpu = cpu_count() or 1
    threads = max(1, cpu - headroom)
    items_path = items_path or Path(DEFAULT_ITEMS_PATH)
    sql_kwargs = {"data_dir": str(data_dir), "items_path": str(items_path)}
    build_sql = Template((SQL_DIR / "build.sql").read_text()).substitute(**sql_kwargs)
    skins_sql = Template((SQL_DIR / "skins.sql").read_text()).substitute(**sql_kwargs)
    count_parquet = Template((SQL_DIR / "count_parquet.sql").read_text()).substitute(**sql_kwargs)
    count_prices = (SQL_DIR / "count_prices.sql").read_text()

    with connect(str(db_path)) as conn:
        conn.execute(f"SET threads = {threads}")
        expected = cast(int, conn.sql(count_parquet).pl().item())
        conn.execute(build_sql)
        conn.execute(skins_sql)
        actual = cast(int, conn.sql(count_prices).pl().item())

        if actual != expected:
            msg = f"Parquet ({expected:,}) != prices ({actual:,})"
            raise ValueError(msg)

    for f in data_dir.glob("*.parquet"):
        f.unlink()

    items_path.unlink(missing_ok=True)

    return {"rows": actual}
