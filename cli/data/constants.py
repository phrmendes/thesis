from pathlib import Path
from typing import Final

BASE_URL: Final[str] = "https://prices.csgotrader.app"
ITEMS_URL: Final[str] = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/{language}/all.json"
SQL_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "sql"
DEFAULT_START: Final[str] = "2020-11-02"
DEFAULT_END: Final[str] = "2023-10-30"
DEFAULT_DATA_DIR: Final[str] = "files"
DEFAULT_DB_PATH: Final[str] = f"{DEFAULT_DATA_DIR}/csgo.duckdb"
DEFAULT_ITEMS_PATH: Final[str] = f"{DEFAULT_DATA_DIR}/items.json"
DEFAULT_CONCURRENCY: Final[int] = 10
DEFAULT_HEADROOM: Final[int] = 3
DEFAULT_LANGUAGE: Final[str] = "en"
HTTP_TIMEOUT: Final[float] = 30.0

RETRY_ATTEMPTS: Final[int] = 5
RETRY_WAIT_MULTIPLIER: Final[int] = 1
RETRY_WAIT_MIN: Final[int] = 1
RETRY_WAIT_MAX: Final[int] = 30
