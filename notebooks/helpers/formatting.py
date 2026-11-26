from textwrap import wrap
from typing import TYPE_CHECKING

import polars as pl
from great_tables.vals import fmt_percent
from helpers.parameters import parameters

if TYPE_CHECKING:
    from pathlib import Path

    from great_tables import GT

HELPER_PARAMETERS = parameters().helpers
LOCALE = HELPER_PARAMETERS.locale
FONT_FAMILY = HELPER_PARAMETERS.font_family
DATE_FORMAT = HELPER_PARAMETERS.date_format
TABLE_SOURCE = HELPER_PARAMETERS.table_source
CHART_NOTE_CHARACTER_WIDTH = 6


def build_cap_text() -> str:
    """Write the configured return cap as a localized percentage.

    Returns:
        The formatted cap.

    """
    return pl.select(fmt_percent(pl.lit(parameters().clean.return_cap), decimals=0, locale=LOCALE)).item()


def wrap_chart_note(*sentences: str) -> list[str]:
    """Join the sentences of a chart note into one paragraph and wrap it to the chart width.

    Vega draws a title as separate lines and does not wrap text.

    Returns:
        The lines of the paragraph.

    """
    return wrap(" ".join(sentences), width=HELPER_PARAMETERS.chart_width // CHART_NOTE_CHARACTER_WIDTH)


def build_metric_table(metrics: pl.DataFrame, labels: dict[str, str]) -> pl.DataFrame:
    """Reshape formatted one-row values and apply their display labels.

    Returns:
        One row per label, in label order, with missing values shown as "n/d".

    """
    metric_name = pl.col("metric_name").replace_strict(labels, return_dtype=pl.String)

    return (
        metrics.select(*labels)
        .unpivot(variable_name="metric_name", value_name="metric_value")
        .with_columns(metric_name)
        .fill_null("n/d")
    )


def write_latex_table(table: GT, path: Path) -> Path:
    """Write one great-tables table as a full-width LaTeX longtable without a title.

    `thesis.md` adds the numbered title with the insertGreatTable command.

    Returns:
        The path of the written file.

    """
    path.write_text(table.tab_options(table_width="100%").as_latex(use_longtable=True), encoding="utf-8")

    return path
