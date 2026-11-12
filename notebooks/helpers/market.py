from datetime import date

import polars as pl
from helpers.frames import record_frame
from helpers.params import load_params
from helpers.statistics import adf_test, arch_test, autocorrelations

LAGS = (1, 2, 3, 7)

REGIMES = ("training", "testing", "pre_cs2", "post_cs2")

REGIME_TYPE = pl.Enum(REGIMES)

MIN_ADF_DAYS = 50


def market_series(prices: pl.DataFrame) -> pl.DataFrame:
    """Build the market series: the equal-weight and price-weighted daily returns, the asset count, and the index.

    The price weight is the price of the previous observed day, the base of the return.
    The first day has no previous price, so its price-weighted return is null.
    The index compounds the mean log return, not the mean simple return.
    The mean simple return of noisy prices holds about half of their variance, so its index grows without a real gain.

    Returns:
        One row per day with the market return, the price-weighted return, the assets, and the index.

    """
    weight = pl.col("price").shift(1).over("name")
    weight_sum = pl.col("weight").sum()
    market_return = pl.col("return").mean().alias("market_return")
    weighted_mean = (pl.col("return") * pl.col("weight")).sum() / weight_sum
    weighted_return = pl.when(weight_sum > 0).then(weighted_mean).alias("weighted_return")
    log_return = (1 + pl.col("return")).log().mean().alias("market_log_return")
    assets = pl.col("return").count().alias("assets")
    weighted = prices.sort("name", "date").with_columns(weight.alias("weight")).drop_nulls("return")
    daily = weighted.group_by("date").agg(market_return, weighted_return, log_return, assets).sort("date")
    market_index = pl.col("market_log_return").cum_sum().exp().alias("market_index")

    return daily.with_columns(market_index)


def market_with_volatility(market: pl.DataFrame) -> pl.DataFrame:
    """Add the rolling standard deviation of the market return.

    Returns:
        The market series with a volatility column.

    """
    window = load_params()["charts"]["volatility_days"]
    volatility = pl.col("market_return").rolling_std(window).alias("volatility")

    return market.sort("date").with_columns(volatility)


def panel_autocorrelation(prices: pl.DataFrame, lag: int) -> float:
    """Return the within-asset autocorrelation of the daily return at one lag.

    A pair needs two returns exactly `lag` days apart, so no gap enters the pairs.

    Returns:
        The autocorrelation.

    """
    centered = pl.col("return") - pl.col("return").mean().over("name")
    lagged = pl.col("centered").shift(lag).over("name").alias("lagged")
    lag_gap = (pl.col("date") - pl.col("date").shift(lag).over("name")).dt.total_days().alias("lag_gap")
    returns = prices.sort("name", "date").drop_nulls("return")
    pairs = (
        returns.with_columns(centered.alias("centered")).with_columns(lagged, lag_gap).filter(pl.col("lag_gap") == lag)
    )
    cross_sum = pairs.select((pl.col("centered") * pl.col("lagged")).sum()).item()
    square_sum = pairs.select((pl.col("centered") ** 2).sum()).item()

    return cross_sum / square_sum


def item_market_correlations(prices: pl.DataFrame, market: pl.DataFrame, min_days: int) -> pl.DataFrame:
    """Correlate the daily return of each item with the market return.

    Returns:
        One row per item with enough days and a correlation.

    """
    market_returns = market.select("date", "market_return")
    correlation = pl.corr("return", "market_return").fill_nan(None).alias("correlation")
    returns = prices.drop_nulls("return")
    per_item = returns.join(market_returns, on="date").group_by("name").agg(pl.len().alias("days"), correlation)

    return per_item.filter(pl.col("days") >= min_days).drop_nulls("correlation")


def market_dynamics(prices: pl.DataFrame, market: pl.DataFrame, min_days: int | None = None) -> pl.DataFrame:
    """Summarize the market return, the autocorrelations, the item correlations, and the ADF and ARCH tests.

    Returns:
        One row with the market dynamics metrics.

    """
    min_days = min_days if min_days is not None else load_params()["eda"]["item_min_days"]
    market_return = pl.col("market_return")

    market_stats = market.select(
        market_return.mean().alias("market_mean_return"),
        market_return.std(ddof=0).alias("market_std_return"),
    )

    market_lags = autocorrelations(market["market_return"].to_list(), max(LAGS))
    market_autocorrelation = record_frame({f"market_lag_{lag}": market_lags[lag - 1] for lag in LAGS})
    asset_autocorrelation = record_frame({f"asset_lag_{lag}": panel_autocorrelation(prices, lag) for lag in LAGS})
    correlation = pl.col("correlation")

    correlations = item_market_correlations(prices, market, min_days).select(
        correlation.mean().alias("mean_market_correlation"),
        correlation.median().alias("median_market_correlation"),
    )

    index_statistic, index_p_value = adf_test(market["market_index"].log().to_list())
    return_statistic, return_p_value = adf_test(market["market_return"].to_list())
    arch_statistic, arch_p_value = arch_test(market["market_return"].to_list(), max(LAGS))

    adf_tests = record_frame(
        {
            "adf_index_statistic": index_statistic,
            "adf_index_p_value": index_p_value,
            "adf_return_statistic": return_statistic,
            "adf_return_p_value": return_p_value,
            "arch_statistic": arch_statistic,
            "arch_p_value": arch_p_value,
        }
    )

    return pl.concat(
        [market_stats, market_autocorrelation, asset_autocorrelation, correlations, adf_tests],
        how="horizontal_extend",
    )


def regime_row(prices: pl.DataFrame, market: pl.DataFrame, regime: str) -> pl.DataFrame:
    """Summarize the item returns and the market series of one regime.

    Returns:
        One row with the regime days, the item return statistics, and the market statistics.

    """
    break_day = date.fromisoformat(load_params()["eda"]["regime_break"])
    masks = {
        "training": pl.col("period") == "training",
        "testing": pl.col("period") == "testing",
        "pre_cs2": pl.col("date") < break_day,
        "post_cs2": pl.col("date") >= break_day,
    }
    subset = prices.filter(masks[regime])
    days = subset["date"].unique()
    market = market.filter(pl.col("date").is_in(days))
    market_return = pl.col("market_return")
    returns = pl.col("return")

    items = subset.select(
        pl.lit(regime, dtype=REGIME_TYPE).alias("regime"),
        pl.col("date").min().alias("first_day"),
        pl.col("date").max().alias("last_day"),
        pl.col("date").n_unique().alias("days"),
        pl.col("name").n_unique().alias("assets"),
        returns.mean().alias("mean_return"),
        ((1 + returns).log().mean().exp() - 1).alias("geometric_return"),
        returns.std().alias("std_return"),
    )

    market_stats = market.select(
        market_return.mean().alias("market_mean_return"),
        (pl.col("market_log_return").mean().exp() - 1).alias("market_geometric_return"),
        pl.col("weighted_return").mean().alias("weighted_mean_return"),
        market_return.std().alias("market_std_return"),
    )

    lag_one = autocorrelations(market["market_return"].to_list(), 1)[0]
    adf_p_value = adf_test(market["market_return"].to_list())[1] if market.height >= MIN_ADF_DAYS else None
    tests = record_frame({"market_lag_1": lag_one, "adf_return_p_value": adf_p_value})

    return pl.concat([items, market_stats, tests], how="horizontal_extend")


def regime_summary(prices: pl.DataFrame, market: pl.DataFrame) -> pl.DataFrame:
    """Compare the training days with the testing days, and the days before and after the CS2 release.

    Returns:
        One row per regime.

    """
    return pl.concat([regime_row(prices, market, regime) for regime in REGIMES])
