from pathlib import Path

import polars as pl
from duckdb import connect
from great_tables import GT

from .constants import DAILY_LABELS, DB_PATH, SQL_DIR, TABLES_DIR


def coverage() -> list[Path]:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    with connect(str(DB_PATH)) as conn:
        daily = (
            conn.sql((SQL_DIR / "coverage_daily.sql").read_text())
            .pl()
            .with_columns(pl.col("metric_name").replace(DAILY_LABELS))
        )
        items = conn.sql((SQL_DIR / "coverage_items.sql").read_text()).pl()

    paths: list[Path] = []

    table_daily = (
        GT(daily)
        .tab_header(title="Cobertura Temporal — CS:GO")
        .cols_label(
            metric_name="Métrica",
            metric_value="Valor",
        )
        .as_latex()
    )
    p = TABLES_DIR / "coverage_daily.tex"
    p.write_text(table_daily)
    paths.append(p)

    table_items = (
        GT(items)
        .tab_header(title="Persistência dos Itens — CS:GO")
        .cols_label(weeks_range="Faixa de Semanas", assets="Itens", avg_weeks="Média de Semanas")
        .as_latex()
    )
    p = TABLES_DIR / "coverage_items.tex"
    p.write_text(table_items)
    paths.append(p)

    return paths
