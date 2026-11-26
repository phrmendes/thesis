import numpy as np
import polars as pl
from helpers.parameters import parameters
from helpers.statistics import calculate_ratio, get_column_max, get_column_min
from statsmodels.nonparametric.kde import KDEUnivariate

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

TOP_ASSETS = parameters().returns.top_assets

LARGE_RETURN = parameters().returns.large_return

MEASURE_COLUMNS = ["mean_return", "median_return", "std_return", "geometric_return"]

GRID_POINTS = parameters().returns.grid_points

GRID_PADDING = parameters().returns.grid_padding

DISTRIBUTION_TYPE = pl.Enum(["capped", "raw"])


def build_geometric_mean(column: str) -> pl.Expr:
    """Build the compound daily return of one return column: the exponential of the mean log return, minus one.

    Returns:
        The expression.

    """
    return (1 + pl.col(column)).log().mean().exp() - 1


def build_return_summary() -> list[pl.Expr]:
    """Build the summary expressions of the daily return.

    Returns:
        The mean, median, compound return, extremes, deviation, and negative-day deviation.

    """
    returns = pl.col("return")

    return [
        returns.mean().alias("mean_return"),
        returns.median().alias("median_return"),
        build_geometric_mean("return").alias("geometric_return"),
        get_column_min("return").alias("min_return"),
        get_column_max("return").alias("max_return"),
        returns.std().alias("std_return"),
        returns.filter(returns < 0).std().alias("negative_returns_std"),
    ]


def add_return_ratios(summary: pl.DataFrame) -> pl.DataFrame:
    """Add the daily Sharpe and Sortino ratios.

    Returns:
        The summary with the two ratio columns.

    """
    sharpe = calculate_ratio(pl.col("mean_return"), pl.col("std_return")).alias("sharpe")
    sortino = calculate_ratio(pl.col("mean_return"), pl.col("negative_returns_std")).alias("sortino")

    return summary.with_columns(sharpe, sortino)


def build_pooled_return_row(prices: pl.DataFrame, name: str) -> pl.DataFrame:
    """Summarize every daily return of one frame as a single row.

    Returns:
        One row with the pooled return statistics.

    """
    days_per_asset = (pl.col("return").count() / pl.col("name").n_unique()).alias("n_days")
    pooled = prices.select(*build_return_summary(), days_per_asset)

    return add_return_ratios(pooled).with_columns(pl.lit(name).alias("name"))


def build_asset_return_rows(prices: pl.DataFrame, min_days: int) -> pl.DataFrame:
    """Rank the assets with enough days by their compound daily return.

    Returns:
        One ranked row per asset.

    """
    days = pl.col("return").count().alias("n_days")
    summary = prices.group_by("name").agg(*build_return_summary(), days)
    ranked = add_return_ratios(summary).filter(pl.col("n_days") >= min_days)
    rank = (pl.int_range(pl.len()) + 1).alias("rank_n")

    return ranked.sort("geometric_return", descending=True).with_columns(rank)


def calculate_return_statistics(prices: pl.DataFrame, min_days: int | None = None) -> pl.DataFrame:
    """Summarize daily returns. The top rows are the best items with enough days.

    Returns:
        The top rows, the rest row, and the overall row.

    """
    min_days = min_days if min_days is not None else parameters().helpers.item_min_days
    top = build_asset_return_rows(prices, min_days).head(TOP_ASSETS)
    rest = prices.filter(~pl.col("name").is_in(top["name"].to_list()))
    pooled_rows = [build_pooled_return_row(rest, "rest"), build_pooled_return_row(prices, "overall")]

    return pl.concat([top, *pooled_rows], how="diagonal_relaxed").select(RETURN_TABLE_COLUMNS)


def build_distribution_row(prices: pl.DataFrame, column: str, label: str) -> pl.DataFrame:
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
        build_geometric_mean(column).alias("geometric_mean"),
        returns.std().alias("std"),
        returns.skew().alias("skewness"),
        returns.kurtosis().alias("excess_kurtosis"),
        *quantiles,
        share_above_half,
    )


def summarize_return_distribution(prices: pl.DataFrame) -> pl.DataFrame:
    """Compare the capped daily return with the raw daily return.

    Returns:
        One row per return column.

    """
    capped = build_distribution_row(prices, "return", "capped")
    raw = build_distribution_row(prices, "raw_return", "raw")

    return pl.concat([capped, raw])


def calculate_item_measures(prices: pl.DataFrame, min_days: int | None = None) -> pl.DataFrame:
    """Measure the daily returns of each item with enough return days.

    Returns:
        One row per item with the arithmetic mean, median, sample standard deviation, and geometric mean.

    """
    min_days = min_days if min_days is not None else parameters().helpers.item_min_days
    days = pl.col("return").count().alias("n_days")

    return (
        prices.drop_nulls("return")
        .group_by("name")
        .agg(
            pl.col("return").mean().alias("mean_return"),
            pl.col("return").median().alias("median_return"),
            pl.col("return").std().alias("std_return"),
            build_geometric_mean("return").alias("geometric_return"),
            days,
        )
        .filter(pl.col("n_days") >= min_days)
        .drop("n_days")
    )


def estimate_measure_densities(measures: pl.DataFrame) -> pl.DataFrame:
    """Estimate the density of each measure across items.

    The grid runs from the 1st to the 99th percentile, plus a padding on each side so the tails reach zero.
    Only the standard-deviation grid excludes negative values.

    Returns:
        One row per measure and grid point with the value and the density.

    """
    frames = []

    for column in MEASURE_COLUMNS:
        values = measures[column].drop_nulls().to_numpy()
        low, high = np.percentile(values, parameters().returns.grid_percentiles)
        padding = (high - low) * GRID_PADDING
        start = max(low - padding, 0.0) if column == "std_return" else low - padding
        grid = np.linspace(start, high + padding, GRID_POINTS)
        density = KDEUnivariate(values)
        density.fit()
        frames.append(pl.DataFrame({"measure": column, "value": grid, "density": density.evaluate(grid)}))

    return pl.concat(frames)
