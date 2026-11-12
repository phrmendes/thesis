import polars as pl
from helpers.params import load_params
from helpers.statistics import column_max, column_min, ratio

RETURN_COLUMNS = [
    "mean_return",
    "median_return",
    "geometric_return",
    "min_return",
    "max_return",
    "std_return",
    "negative_returns_std",
]

QUANTILE_LEVELS = {"p01": 0.01, "p05": 0.05, "p50": 0.5, "p95": 0.95, "p99": 0.99}

RETURN_TABLE_COLUMNS = [
    "name",
    "rank_n",
    *RETURN_COLUMNS,
    "n_days",
    "sharpe",
    "sortino",
]

TOP_ASSETS = 10

LARGE_RETURN = 0.5

DISTRIBUTION_TYPE = pl.Enum(["capped", "raw"])


def geometric_mean(column: str) -> pl.Expr:
    """Build the compound daily return of one return column: the exponential of the mean log return, minus one.

    Returns:
        The expression.

    """
    return (1 + pl.col(column)).log().mean().exp() - 1


def return_summary() -> list[pl.Expr]:
    """Build the summary expressions of the daily return.

    Returns:
        The mean, median, compound return, extremes, deviation, and negative-day deviation.

    """
    returns = pl.col("return")

    return [
        returns.mean().alias("mean_return"),
        returns.median().alias("median_return"),
        geometric_mean("return").alias("geometric_return"),
        column_min("return").alias("min_return"),
        column_max("return").alias("max_return"),
        returns.std().alias("std_return"),
        returns.filter(returns < 0).std().alias("negative_returns_std"),
    ]


def with_return_ratios(summary: pl.DataFrame) -> pl.DataFrame:
    """Add the daily Sharpe and Sortino ratios.

    Returns:
        The summary with the two ratio columns.

    """
    sharpe = ratio(pl.col("mean_return"), pl.col("std_return")).alias("sharpe")
    sortino = ratio(pl.col("mean_return"), pl.col("negative_returns_std")).alias("sortino")

    return summary.with_columns(sharpe, sortino)


def pooled_return_row(prices: pl.DataFrame, name: str) -> pl.DataFrame:
    """Summarize every daily return of one frame as a single row.

    Returns:
        One row with the pooled return statistics.

    """
    days_per_asset = (pl.col("return").count() / pl.col("name").n_unique()).alias("n_days")
    pooled = prices.select(*return_summary(), days_per_asset)

    return with_return_ratios(pooled).with_columns(pl.lit(name).alias("name"))


def asset_return_rows(prices: pl.DataFrame, min_days: int) -> pl.DataFrame:
    """Rank the assets with enough days by their compound daily return.

    Returns:
        One ranked row per asset.

    """
    days = pl.col("return").count().alias("n_days")
    summary = prices.group_by("name").agg(*return_summary(), days)
    ranked = with_return_ratios(summary).filter(pl.col("n_days") >= min_days)
    rank = (pl.int_range(pl.len()) + 1).alias("rank_n")

    return ranked.sort("geometric_return", descending=True).with_columns(rank)


def return_statistics(prices: pl.DataFrame, min_days: int | None = None) -> pl.DataFrame:
    """Summarize daily returns. The top rows are the best items with enough days.

    Returns:
        The top rows, the rest row, and the overall row.

    """
    min_days = min_days if min_days is not None else load_params()["eda"]["item_min_days"]
    top = asset_return_rows(prices, min_days).head(TOP_ASSETS)
    rest = prices.filter(~pl.col("name").is_in(top["name"].to_list()))
    pooled_rows = [pooled_return_row(rest, "rest"), pooled_return_row(prices, "overall")]

    return pl.concat([top, *pooled_rows], how="diagonal_relaxed").select(RETURN_TABLE_COLUMNS)


def distribution_row(prices: pl.DataFrame, column: str, label: str) -> pl.DataFrame:
    """Summarize the pooled distribution of one return column.

    Returns:
        One row with the distribution measures.

    """
    returns = pl.col(column)
    quantiles = [returns.quantile(level).alias(name) for name, level in QUANTILE_LEVELS.items()]
    share_above_half = (returns.abs() > LARGE_RETURN).mean().alias("share_above_half")

    return prices.select(
        pl.lit(label, dtype=DISTRIBUTION_TYPE).alias("label"),
        pl.len().alias("n"),
        returns.mean().alias("mean"),
        geometric_mean(column).alias("geometric_mean"),
        returns.std().alias("std"),
        returns.skew().alias("skewness"),
        returns.kurtosis().alias("excess_kurtosis"),
        *quantiles,
        share_above_half,
    )


def return_distribution(prices: pl.DataFrame) -> pl.DataFrame:
    """Compare the capped daily return with the raw daily return.

    Returns:
        One row per return column.

    """
    capped = distribution_row(prices, "return", "capped")
    raw = distribution_row(prices, "raw_return", "raw")

    return pl.concat([capped, raw])
