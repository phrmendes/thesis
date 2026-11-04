import polars as pl
from helpers.frames import bucket_label, with_empty_buckets
from helpers.schemas import SELECTION_REASONS

WEEK_BUCKET_LABELS = ("< 25", "25-49", "50-74", "75-99", "100-124", "125+")

WEEK_BUCKET_BREAKS = (24, 49, 74, 99, 124)


def coverage_weekly(prices: pl.DataFrame) -> pl.DataFrame:
    """Count the assets with a price in each week.

    Returns:
        One row per week with the number of assets.

    """
    return prices.group_by("week").agg(pl.col("name").count().alias("assets")).sort("week")


def observed_weekly_assets(prices: pl.DataFrame) -> pl.DataFrame:
    """Count the assets with a real price in each week.

    Returns:
        One row per week with the asset count.

    Raises:
        SystemExit: The cleaned prices have no observed week.

    """
    observed = prices.filter(pl.col("observed") == 1)
    weekly = coverage_weekly(observed)

    if weekly.is_empty():
        message = "cleaned prices are empty"
        raise SystemExit(message)

    return weekly


def coverage_daily(prices: pl.DataFrame, audit: pl.DataFrame) -> pl.DataFrame:
    """Summarize temporal coverage and assets per week.

    Returns:
        One row with the price dates, the return weeks, the observed share, and the assets per week.

    """
    price_dates = audit.select("first_price_week", "last_price_day")
    assets = pl.col("assets")

    assets_per_week = observed_weekly_assets(prices).select(
        assets.min().alias("min_assets_per_week"),
        assets.mean().alias("avg_assets_per_week"),
        assets.max().alias("max_assets_per_week"),
    )

    return_weeks = prices.select(
        pl.col("week").min().alias("first_return_week"),
        pl.col("week").n_unique().alias("return_weeks"),
        pl.col("observed").mean().alias("asset_week_share"),
    )

    return pl.concat([price_dates, return_weeks, assets_per_week], how="horizontal_extend")


def coverage_items(assets: pl.DataFrame) -> pl.DataFrame:
    """Group the raw assets by their number of weeks with a positive price.

    Returns:
        One row per bucket with the universe and the selected counts.

    """
    weeks_range = bucket_label("positive_weeks", WEEK_BUCKET_BREAKS, WEEK_BUCKET_LABELS).alias("weeks_range")
    universe_assets = pl.len().alias("universe_assets")
    selected_assets = (pl.col("reason") == "selected").sum().alias("selected_assets")
    counts = assets.group_by(weeks_range).agg(universe_assets, selected_assets)

    return with_empty_buckets(counts, "weeks_range", WEEK_BUCKET_LABELS)


def launch_period_groups(assets: pl.DataFrame) -> pl.DataFrame:
    """Count the raw assets by launch half-year, with the selection result.

    Returns:
        One row per launch period with the reason counts.

    """
    year = pl.col("first_week").dt.year()
    half = (pl.col("first_week").dt.month() - 1) // 6 + 1
    launch_period = pl.concat_str(year, pl.lit("-H"), half).alias("launch_period")
    reason_counts = [(pl.col("reason") == reason).sum().alias(reason) for reason in SELECTION_REASONS]

    grouped = assets.group_by(launch_period).agg(pl.len().alias("assets"), *reason_counts).sort("launch_period")

    return grouped.with_columns(pl.col("launch_period").cast(pl.Categorical))


def quality_metrics(prices: pl.DataFrame) -> pl.DataFrame:
    """Summarize size, return signs, coverage, and metric availability.

    Returns:
        One row with the quality metrics.

    """
    returns = pl.col("return")
    weeks = pl.col("weeks")

    weeks_per_asset = (
        prices.group_by("name")
        .agg(pl.col("observed").sum().alias("weeks"))
        .select(
            weeks.min().alias("min_weeks_per_asset"),
            weeks.mean().alias("avg_weeks_per_asset"),
            weeks.max().alias("max_weeks_per_asset"),
        )
    )

    totals = prices.select(
        pl.len().alias("records"),
        pl.col("name").n_unique().alias("assets"),
        pl.col("week").n_unique().alias("weeks"),
        (returns > 0).sum().alias("positive_return_weeks"),
        (returns < 0).sum().alias("negative_return_weeks"),
        (returns == 0.0).sum().alias("zero_return_weeks"),
        (pl.len() - pl.col("observed").sum()).alias("filled_rows"),
    )

    return pl.concat([totals, weeks_per_asset], how="horizontal_extend")
