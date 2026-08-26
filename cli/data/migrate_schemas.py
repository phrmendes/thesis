from pathlib import Path
from typing import cast

from duckdb import connect

from .constants import DEFAULT_DB_PATH, SQL_DIR


def migrate_schemas(db_path: Path | None = None) -> bool:
    """Move raw, cleaned, and strategy tables into their schemas."""
    db_path = db_path or Path(DEFAULT_DB_PATH)
    status_query = (SQL_DIR / "has_schemas.sql").read_text()
    migration_query = (SQL_DIR / "migrate_schemas.sql").read_text()

    with connect(str(db_path)) as conn:
        if cast(bool, conn.sql(status_query).pl().item()):
            return False
        conn.begin()
        conn.execute(migration_query)
        conn.commit()
        return True
