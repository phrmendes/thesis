import polars as pl
from helpers.parameters import parameters

EXPENSIVE_PRICE = parameters().helpers.expensive_price

SOURCE_TYPE = pl.Enum(["steam_7d", "composite", "composite_800", "buff"])


def calculate_source_returns(prices: pl.DataFrame, column: str) -> pl.DataFrame:
    """Build the capped daily return of one source price, between two consecutive days with a source price.

    Returns:
        The rows of the source with a `source_return` column. Rows without a return are out.

    """
    clean_parameters = parameters().clean
    sources = prices.drop_nulls(column).sort("name", "date")
    previous = pl.col(column).shift(1).over("name")
    gap = (pl.col("date") - pl.col("date").shift(1).over("name")).dt.total_days()
    source_return = (pl.col(column) / previous - 1).clip(-clean_parameters.return_cap, clean_parameters.return_cap)

    return (
        sources.with_columns(source_return.alias("source_return"), gap.alias("gap"))
        .filter(pl.col("gap") <= clean_parameters.max_gap_days)
        .drop_nulls("source_return")
    )


def build_source_row(prices: pl.DataFrame, column: str, label: str) -> pl.DataFrame:
    """Compare one source price with the main price: day share, median price ratio, and return correlation.

    Returns:
        One row of the sources table.

    """
    day_share = (pl.col(column).count() / pl.len()).alias("day_share")
    price_ratio = (pl.col("price") / pl.col(column)).median().alias("median_ratio")
    totals = prices.select(pl.lit(label, dtype=SOURCE_TYPE).alias("source"), day_share, price_ratio)
    correlation = pl.corr("return", "source_return").fill_nan(None).alias("return_correlation")
    pairs = calculate_source_returns(prices, column).drop_nulls("return").select(correlation, pl.len().alias("pairs"))

    return pl.concat([totals, pairs], how="horizontal_extend")


def compare_sources(prices: pl.DataFrame) -> pl.DataFrame:
    """Compare the main price with the Steam 7-day price and the csgotrader and BUFF daily prices.

    Returns:
        One row per source.

    """
    steam_7d = build_source_row(prices, "price_7d", "steam_7d")
    expensive = prices.filter(pl.col("price") >= EXPENSIVE_PRICE)
    composite = build_source_row(prices, "composite_price", "composite")
    composite_expensive = build_source_row(expensive, "composite_price", "composite_800")
    buff = build_source_row(prices, "buff_price", "buff")

    return pl.concat([steam_7d, composite, composite_expensive, buff])
