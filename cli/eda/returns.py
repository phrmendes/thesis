from pathlib import Path

import polars as pl
from duckdb import connect
from great_tables import GT

from .constants import DB_PATH, LABEL_MAP, RETURN_COLUMNS, SQL_DIR, TABLES_DIR


def returns() -> Path:
    query = (SQL_DIR / "summarize_weekly_return_statistics.sql").read_text()
    with connect(str(DB_PATH)) as conn:
        df = conn.sql(query).pl().with_columns(pl.col("name").replace(LABEL_MAP))

    table = (
        GT(df)
        .tab_header(title="Estatísticas dos Retornos — Itens CS:GO")
        .fmt_percent(columns=RETURN_COLUMNS, decimals=2)
        .fmt_number(columns=["n_weeks"], decimals=1)
        .fmt_number(columns=["sharpe", "sortino"], decimals=2)
        .tab_spanner(label="Retornos", columns=RETURN_COLUMNS)
        .cols_label(
            name="Item",
            mean_return="Média",
            median_return="Mediana",
            min_return="Mínimo",
            max_return="Máximo",
            std_return="Desvio Padrão",
            negative_returns_std="Desvio Padrão (negativos)",
            n_weeks="Semanas",
            sharpe="Sharpe",
            sortino="Sortino",
        )
        .cols_hide("rank_n")
        .as_latex()
    )

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLES_DIR / "returns.tex"
    path.write_text(table)
    return path
