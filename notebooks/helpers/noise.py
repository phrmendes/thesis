import polars as pl
from helpers.frames import record_frame

WINDOW_DAYS = 7


def with_variance_ratio_terms(frame: pl.DataFrame, group: str | None) -> pl.DataFrame:
    """Add the log return and its sum over seven consecutive days.

    A window counts only when its seven rows span exactly seven days. A gap in the days drops the window.

    Returns:
        The frame with `log_return` and `window_return`, null where the window has a gap.

    """
    ordered = frame.sort(group, "date") if group else frame.sort("date")
    window = pl.col("log_return").rolling_sum(WINDOW_DAYS)
    first_day = pl.col("date").shift(WINDOW_DAYS - 1)

    if group:
        window = window.over(group)
        first_day = first_day.over(group)

    span = (pl.col("date") - first_day).dt.total_days()
    window_return = pl.when(span == WINDOW_DAYS - 1).then(window).alias("window_return")

    return ordered.with_columns(window_return)


def variance_ratio() -> pl.Expr:
    """Build the variance ratio of the window return: its variance over the window length times the daily variance.

    A ratio below one points to mean reversion, as bid-ask bounce makes.

    Returns:
        The expression.

    """
    return pl.col("window_return").var() / (WINDOW_DAYS * pl.col("log_return").var())


def item_noise(prices: pl.DataFrame) -> pl.DataFrame:
    """Measure the first-order autocovariance, the Roll spread, and the variance ratio of each item.

    The Roll spread is two times the square root of minus the autocovariance, when the autocovariance is negative.

    Returns:
        One row per item.

    """
    returns = prices.drop_nulls("return").with_columns((1 + pl.col("return")).log().alias("log_return"))
    ordered = with_variance_ratio_terms(returns, "name")
    lagged = pl.col("log_return").shift(1).over("name")
    lag_gap = (pl.col("date") - pl.col("date").shift(1).over("name")).dt.total_days()
    pairs = ordered.with_columns(lagged.alias("lagged"), lag_gap.alias("lag_gap")).with_columns(
        pl.when(pl.col("lag_gap") == 1).then(pl.col("lagged")).alias("lagged")
    )
    autocovariance = pl.cov(pl.col("log_return"), pl.col("lagged")).alias("autocovariance")

    return pairs.group_by("name").agg(
        pl.len().alias("days"),
        autocovariance,
        variance_ratio().alias("variance_ratio"),
    )


def price_noise(prices: pl.DataFrame, market: pl.DataFrame, min_days: int) -> pl.DataFrame:
    """Test the prices for noise: bid-ask bounce makes a negative autocovariance and a variance ratio below one.

    Returns:
        One row with the item count, the share of items with a negative autocovariance, the median Roll spread,
        the median item variance ratio, and the variance ratio of the market return.

    """
    items = item_noise(prices).filter(pl.col("days") >= min_days)
    roll_spread = pl.when(pl.col("autocovariance") < 0).then(2 * (-pl.col("autocovariance")).sqrt())

    item_summary = items.select(
        pl.len().alias("items"),
        (pl.col("autocovariance") < 0).mean().alias("negative_autocovariance_share"),
        roll_spread.median().alias("median_roll_spread"),
        pl.col("variance_ratio").median().alias("median_variance_ratio"),
    )

    market_log_returns = market.select("date", pl.col("market_log_return").alias("log_return"))
    market_frame = with_variance_ratio_terms(market_log_returns, None)
    market_ratio = record_frame({"market_variance_ratio": market_frame.select(variance_ratio()).item()})

    return pl.concat([item_summary, market_ratio], how="horizontal_extend")
