from pathlib import Path
from typing import Final

DB_PATH: Final[Path] = Path("files/csgo.duckdb")
TABLES_DIR: Final[Path] = Path("tex/tables")
SQL_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "sql" / "eda"

LABEL_MAP: Final[dict[str, str]] = {"rest": "Restante", "overall": "Geral"}

RETURN_COLUMNS: Final[list[str]] = [
    "mean_return",
    "median_return",
    "min_return",
    "max_return",
    "std_return",
    "negative_returns_std",
]

DAILY_LABELS: Final[dict[str, str]] = {
    "start_date": "Data de início",
    "end_date": "Data de fim",
    "observed_weeks": "Semanas observadas",
    "total_weeks": "Total de semanas",
    "coverage": "Cobertura",
    "min_assets_per_week": "Mín. ativos/semana",
    "avg_assets_per_week": "Média ativos/semana",
    "max_assets_per_week": "Máx. ativos/semana",
}

METRIC_LABELS: Final[dict[str, str]] = {
    "records": "Registros",
    "assets": "Ativos distintos",
    "weeks": "Semanas distintas",
    "min_weeks_per_asset": "Mín. semanas/ativo",
    "avg_weeks_per_asset": "Média semanas/ativo",
    "max_weeks_per_asset": "Máx. semanas/ativo",
    "positive_return_weeks": "Semanas com retorno positivo",
    "negative_return_weeks": "Semanas com retorno negativo",
    "records_with_sharpe": "Registros com Sharpe definido",
}
