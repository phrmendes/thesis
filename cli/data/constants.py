from pathlib import Path

BASE_URL = "https://prices.csgotrader.app"
ITEMS_URL = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/{language}/all.json"
SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "data"
DEFAULT_START = "2020-11-02"
DEFAULT_END = "2023-10-30"
DEFAULT_DATA_DIR = "files"
DEFAULT_DB_PATH = f"{DEFAULT_DATA_DIR}/csgo.duckdb"
DEFAULT_ITEMS_PATH = f"{DEFAULT_DATA_DIR}/items.json"
DEFAULT_CONCURRENCY = 10
DEFAULT_HEADROOM = 3
