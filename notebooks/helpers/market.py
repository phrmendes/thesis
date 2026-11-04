import polars as pl
from helpers.frames import record_frame
from helpers.params import load_params
from helpers.statistics import adf_test, autocorrelations

LAGS = range(1, 5)


def market_series(prices: pl.DataFrame) -> pl.DataFrame:
    """Build the equal-weight market series: the mean weekly return, the asset count, and the index.

    Returns:
        One row per week with the market return, the assets, and the index.

    """
    market_return = pl.col("return").mean().alias("market_return")
    assets = pl.col("name").count().alias("assets")
    weekly = prices.group_by("week").agg(market_return, assets).sort("week")
    market_index = (1 + pl.col("market_return")).cum_prod().alias("market_index")

    return weekly.with_columns(market_index)


def market_with_volatility(market: pl.DataFrame) -> pl.DataFrame:
    """Add the rolling standard deviation of the market return.

    Returns:
        The market series with a volatility column.

    """
    window = load_params()["charts"]["volatility_weeks"]
    volatility = pl.col("market_return").rolling_std(window).alias("volatility")

    return market.sort("week").with_columns(volatility)


def panel_autocorrelation(prices: pl.DataFrame, lag: int) -> float:
    """Return the within-asset autocorrelation of the weekly return at one lag.

    Returns:
        The autocorrelation.

    """
    centered = pl.col("return") - pl.col("return").mean().over("name")
    lagged = pl.col("centered").shift(lag).over("name")
    pairs = prices.with_columns(centered.alias("centered")).with_columns(lagged.alias("lagged")).drop_nulls("lagged")
    cross_sum = pairs.select((pl.col("centered") * pl.col("lagged")).sum()).item()
    square_sum = pairs.select((pl.col("centered") ** 2).sum()).item()

    return cross_sum / square_sum


def item_market_correlations(prices: pl.DataFrame, market: pl.DataFrame, min_weeks: int) -> pl.DataFrame:
    """Correlate the weekly return of each item with the market return.

    Returns:
        One row per item with enough weeks and a correlation.

    """
    market_returns = market.select("week", "market_return")
    correlation = pl.corr("return", "market_return").fill_nan(None).alias("correlation")
    per_item = prices.join(market_returns, on="week").group_by("name").agg(pl.len().alias("weeks"), correlation)

    return per_item.filter(pl.col("weeks") >= min_weeks).drop_nulls("correlation")


def market_dynamics(prices: pl.DataFrame, market: pl.DataFrame, min_weeks: int | None = None) -> pl.DataFrame:
    """Summarize the market return, the autocorrelations, the item correlations, and the ADF tests.

    Returns:
        One row with the market dynamics metrics.

    """
    min_weeks = min_weeks if min_weeks is not None else load_params()["eda"]["item_min_weeks"]
    market_return = pl.col("market_return")

    market_stats = market.select(
        market_return.mean().alias("market_mean_return"),
        market_return.std(ddof=0).alias("market_std_return"),
    )

    market_lags = autocorrelations(market["market_return"].to_list(), max(LAGS))
    market_autocorrelation = record_frame({f"market_lag_{lag}": market_lags[lag - 1] for lag in LAGS})
    asset_autocorrelation = record_frame({f"asset_lag_{lag}": panel_autocorrelation(prices, lag) for lag in LAGS})
    correlation = pl.col("correlation")

    correlations = item_market_correlations(prices, market, min_weeks).select(
        correlation.mean().alias("mean_market_correlation"),
        correlation.median().alias("median_market_correlation"),
    )

    index_statistic, index_p_value = adf_test(market["market_index"].log().to_list())
    return_statistic, return_p_value = adf_test(market["market_return"].to_list())

    adf_tests = record_frame(
        {
            "adf_index_statistic": index_statistic,
            "adf_index_p_value": index_p_value,
            "adf_return_statistic": return_statistic,
            "adf_return_p_value": return_p_value,
        }
    )

    return pl.concat(
        [market_stats, market_autocorrelation, asset_autocorrelation, correlations, adf_tests],
        how="horizontal_extend",
    )
