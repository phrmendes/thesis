import polars as pl
from helpers.params import load_params

EXPENSIVE_PRICE = 800


def source_return(column: str) -> pl.Expr:
    """Build the capped weekly return of one source close.

    Returns:
        The return expression, named `source_return`.

    """
    cap = load_params()["clean"]["return_cap"]
    previous = pl.col(column).shift(1).over("name")

    return (pl.col(column) / previous - 1).clip(-cap, cap).alias("source_return")


def source_row(prices: pl.DataFrame, column: str, label: str) -> pl.DataFrame:
    """Compare one source close with the main price: week share, median price ratio, and return correlation.

    Returns:
        One row of the sources table.

    """
    is_observed = pl.col("observed") == 1
    observed = prices.filter(is_observed)
    week_share = (pl.col(column).count() / pl.len()).fill_nan(None).alias("week_share")
    price_ratio = (pl.col("price") / pl.col(column)).median().alias("median_ratio")
    totals = observed.select(pl.lit(label).alias("source"), week_share, price_ratio)
    returns = prices.with_columns(source_return(column)).filter(is_observed & pl.col("source_return").is_not_null())
    correlation = pl.corr("return", "source_return").fill_nan(None).alias("return_correlation")
    pairs = returns.select(correlation, pl.len().alias("pairs"))

    return pl.concat([totals, pairs], how="horizontal_extend")


def source_comparison(prices: pl.DataFrame) -> pl.DataFrame:
    """Compare the main price with the Steam and BUFF weekly closes.

    Returns:
        One row per source.

    """
    expensive = prices.filter(pl.col("price") >= EXPENSIVE_PRICE)
    composite = source_row(prices, "composite_close", "composite")
    composite_expensive = source_row(expensive, "composite_close", "composite_800")
    buff = source_row(prices, "buff_close", "buff")

    return pl.concat([composite, composite_expensive, buff])
