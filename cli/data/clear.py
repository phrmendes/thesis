from pathlib import Path
from typing import cast

from duckdb import connect

from .constants import DEFAULT_DB_PATH, SQL_DIR


def clear(db_path: Path | None = None) -> int:
    """Build the cleaned price table from the raw prices table."""
    db_path = db_path or Path(DEFAULT_DB_PATH)
    query = (SQL_DIR / "build_cleaned_prices.sql").read_text()

    with connect(str(db_path)) as conn:
        conn.execute(query)
        return cast(int, conn.sql("SELECT count(*) FROM cleaned.prices").pl().item())
