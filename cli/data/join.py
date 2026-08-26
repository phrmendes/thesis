from pathlib import Path
from typing import cast

from duckdb import connect

from .constants import DEFAULT_DB_PATH, SQL_DIR


def join(db_path: Path | None = None) -> int:
    """Join prices with rarity and keep only the resulting prices table."""
    db_path = db_path or Path(DEFAULT_DB_PATH)
    query = (SQL_DIR / "attach_rarity_to_raw_prices.sql").read_text()
    count_query = (SQL_DIR / "count_raw_price_rows.sql").read_text()

    with connect(str(db_path)) as conn:
        conn.begin()
        conn.execute(query)
        conn.commit()

    with connect(str(db_path), read_only=True) as conn:
        return cast(int, conn.sql(count_query).pl().item())
