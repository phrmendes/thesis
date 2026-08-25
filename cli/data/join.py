from pathlib import Path
from typing import cast

from duckdb import connect

from .constants import DEFAULT_DB_PATH, SQL_DIR


def join(db_path: Path | None = None) -> int:
    """Join prices with rarity and keep only the resulting prices table."""
    db_path = db_path or Path(DEFAULT_DB_PATH)
    query = (SQL_DIR / "join.sql").read_text()

    with connect(str(db_path)) as conn:
        conn.execute("BEGIN TRANSACTION")

        try:
            conn.execute(query)
            conn.execute("DROP TABLE prices")
            conn.execute("DROP TABLE skins")
            conn.execute("ALTER TABLE prices_joined RENAME TO prices")
            rows = cast(int, conn.sql("SELECT count(*) FROM prices").pl().item())
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    return rows
