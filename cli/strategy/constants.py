from pathlib import Path
from typing import Final

from ..data.constants import DEFAULT_DB_PATH as DATA_DEFAULT_DB_PATH

DEFAULT_DB_PATH: Final[str] = DATA_DEFAULT_DB_PATH
DEFAULT_ROI: Final[float] = 0.05
DEFAULT_SHARPE: Final[float] = 0.10
DEFAULT_SORTINO: Final[float] = 0.20
SQL_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "sql" / "strategies"
