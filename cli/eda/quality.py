from pathlib import Path

import polars as pl
from duckdb import connect
from great_tables import GT

from .constants import DB_PATH, METRIC_LABELS, SQL_DIR, TABLES_DIR


def quality() -> Path:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    with connect(str(DB_PATH)) as conn:
        stats = (
            conn.sql((SQL_DIR / "summarize_cleaned_data_quality.sql").read_text())
            .pl()
            .with_columns(pl.col("metric_name").replace(METRIC_LABELS))
        )

    table = (
        GT(stats)
        .tab_header(title="Qualidade do Dataset Limpo — CS:GO")
        .cols_label(
            metric_name="Métrica",
            metric_value="Valor",
        )
        .as_latex()
    )
    p = TABLES_DIR / "quality.tex"
    p.write_text(table)
    return p
