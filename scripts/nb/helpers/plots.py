import os
from typing import TYPE_CHECKING

import altair as alt
import polars as pl
import vl_convert as vlc

if TYPE_CHECKING:
    from pathlib import Path

type ChartType = alt.Chart | alt.VConcatChart

EVENTS = [{"name": "CS2", "date": "2023-03-22"}]
VOLATILITY_WEEKS = 13
BIN_WIDTH = 0.05
RAW_CEILING = 5.0
CHART_FONT = "Liberation Serif"
FONT_DIRECTORY = os.environ.get("THESIS_FONT_DIR", "")
PT_BR_TIME_LOCALE = {
    "dateTime": "%A, %e de %B de %Y, %X",
    "date": "%d/%m/%Y",
    "time": "%H:%M:%S",
    "periods": ["AM", "PM"],
    "days": ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"],
    "shortDays": ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"],
    "months": [
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ],
    "shortMonths": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
}

EVENTS = [{"name": "CS2", "date": "2023-03-22"}]
VOLATILITY_WEEKS = 13
BIN_WIDTH = 0.05
RAW_CEILING = 5.0


def coverage_chart(source: Path) -> ChartType:
    """Draw how many assets have a price in each week."""
    weekly = pl.read_parquet(source).group_by("week").agg(pl.col("name").count().alias("assets")).sort("week")
    return (
        alt.Chart(weekly)
        .mark_line()
        .encode(
            x=alt.X("week:T", title="Semana"),
            y=alt.Y("assets:Q", title="Ativos"),
        )
        .properties(width=640, height=360)
    )


def market_chart(source: Path) -> ChartType:
    """Draw the market index and its rolling volatility with the event dates."""
    frame = (
        pl.read_parquet(source)
        .sort("week")
        .with_columns(pl.col("market_return").rolling_std(VOLATILITY_WEEKS).alias("volatility"))
    )

    events = pl.DataFrame(EVENTS).with_columns(pl.col("date").str.to_date())
    rules = alt.Chart(events).mark_rule(color="red", strokeDash=[4, 4]).encode(x="date:T")

    index = (
        alt.Chart(frame)
        .mark_line()
        .encode(
            x=alt.X("week:T", title="Semana"),
            y=alt.Y(
                "market_index:Q",
                title="Índice (início = 1)",
                scale=alt.Scale(type="log", zero=False),
            ),
        )
    )

    volatility = (
        alt.Chart(frame)
        .mark_line()
        .encode(
            x=alt.X("week:T", title="Semana"),
            y=alt.Y("volatility:Q", title=f"Desvio padrão ({VOLATILITY_WEEKS} semanas)"),
        )
    )

    return alt.vconcat(
        (index + rules).properties(width=640, height=220),
        (volatility + rules).properties(width=640, height=140),
    )


def returns_chart(source: Path) -> ChartType:
    """Draw the histogram of the capped and the raw weekly returns."""
    prices = pl.read_parquet(source)
    series = {
        "Limitado": prices["return"],
        "Bruto": prices["raw_return"].clip(upper_bound=RAW_CEILING),
    }

    bins = pl.concat(
        [
            pl.DataFrame({"retorno": values, "serie": label})
            .with_columns(((pl.col("retorno") / BIN_WIDTH).floor() * BIN_WIDTH).alias("faixa"))
            .group_by("serie", "faixa")
            .agg(pl.len().alias("itens_semana"))
            for label, values in series.items()
        ]
    ).sort("serie", "faixa")

    return (
        alt.Chart(bins)
        .mark_line(point=True, interpolate="step-after")
        .encode(
            x=alt.X("faixa:Q", title="Retorno semanal (bruto limitado em 500%)"),
            y=alt.Y("itens_semana:Q", title="Itens-semana", scale=alt.Scale(type="log")),
            color=alt.Color("serie:N", title="Retorno"),
        )
        .properties(width=640, height=360)
    )


def build_charts(prices: Path, market: Path) -> dict[str, ChartType]:
    """Build every chart from the parquet files.

    Returns:
        The charts, keyed by chart name.

    """
    return {
        "coverage": coverage_chart(prices),
        "market": market_chart(market),
        "returns_histogram": returns_chart(prices),
    }


def write_charts(charts: dict[str, ChartType], output: Path) -> list[Path]:
    """Write every chart as a PDF file, because lualatex cannot read an SVG.

    Returns:
        The path of each written file.

    """
    output.mkdir(parents=True, exist_ok=True)
    written = []

    if FONT_DIRECTORY:
        vlc.register_font_directory(FONT_DIRECTORY)

    for name, chart in charts.items():
        path = output / f"{name}.pdf"
        pdf = vlc.vegalite_to_pdf(
            chart.to_dict(),
            config={"font": CHART_FONT},
            time_format_locale=PT_BR_TIME_LOCALE,
        )
        path.write_bytes(pdf)
        print(f"Written {path}")
        written.append(path)

    return written
