import polars as pl
from helpers.frames import bucket_label, with_empty_buckets
from helpers.schemas import SELECTION_REASONS

DAY_BUCKET_LABELS = ("< 200", "200-399", "400-599", "600-799", "800-999", "1000+")

DAY_BUCKET_BREAKS = (199, 399, 599, 799, 999)


def coverage_by_day(prices: pl.DataFrame) -> pl.DataFrame:
    """Count the assets with a price on each day.

    Returns:
        One row per day with the number of assets.

    Raises:
        SystemExit: The cleaned prices are empty.

    """
    if prices.is_empty():
        message = "cleaned prices are empty"
        raise SystemExit(message)

    return prices.group_by("date").agg(pl.col("name").count().alias("assets")).sort("date")


def coverage_daily(prices: pl.DataFrame, audit: pl.DataFrame) -> pl.DataFrame:
    """Summarize temporal coverage and assets per day.

    Returns:
        One row with the price dates, the days, the return share, and the assets per day.

    """
    price_dates = audit.select("first_price_day", "last_price_day")
    assets = pl.col("assets")

    assets_per_day = coverage_by_day(prices).select(
        assets.min().alias("min_assets_per_day"),
        assets.mean().alias("avg_assets_per_day"),
        assets.max().alias("max_assets_per_day"),
    )

    days = prices.select(
        pl.col("date").n_unique().alias("price_days"),
        pl.col("date").filter(pl.col("return").is_not_null()).min().alias("first_return_day"),
        pl.col("return").is_not_null().mean().alias("return_row_share"),
    )

    return pl.concat([price_dates, days, assets_per_day], how="horizontal_extend")


def coverage_items(assets: pl.DataFrame) -> pl.DataFrame:
    """Group the raw assets by their number of days with a positive price.

    Returns:
        One row per bucket with the universe and the selected counts.

    """
    days_range = bucket_label("positive_days", DAY_BUCKET_BREAKS, DAY_BUCKET_LABELS).alias("days_range")
    universe_assets = pl.len().alias("universe_assets")
    selected_assets = (pl.col("reason") == "selected").sum().alias("selected_assets")
    counts = assets.group_by(days_range).agg(universe_assets, selected_assets)

    return with_empty_buckets(counts, "days_range", DAY_BUCKET_LABELS)


def launch_period_groups(assets: pl.DataFrame) -> pl.DataFrame:
    """Count the raw assets by launch half-year, with the selection result.

    Returns:
        One row per launch period with the reason counts.

    """
    year = pl.col("first_date").dt.year()
    half = (pl.col("first_date").dt.month() - 1) // 6 + 1
    launch_period = pl.concat_str(year, pl.lit("-H"), half).alias("launch_period")
    reason_counts = [(pl.col("reason") == reason).sum().alias(reason) for reason in SELECTION_REASONS]

    grouped = assets.group_by(launch_period).agg(pl.len().alias("assets"), *reason_counts).sort("launch_period")

    return grouped.with_columns(pl.col("launch_period").cast(pl.Categorical))


def quality_metrics(prices: pl.DataFrame) -> pl.DataFrame:
    """Summarize size, return signs, and the days with no return.

    Returns:
        One row with the quality metrics.

    """
    returns = pl.col("return")
    days = pl.col("days")

    days_per_asset = (
        prices.group_by("name")
        .agg(pl.len().alias("days"))
        .select(
            days.min().alias("min_days_per_asset"),
            days.mean().alias("avg_days_per_asset"),
            days.max().alias("max_days_per_asset"),
        )
    )

    totals = prices.select(
        pl.len().alias("records"),
        pl.col("name").n_unique().alias("assets"),
        pl.col("date").n_unique().alias("days"),
        (returns > 0).sum().alias("positive_return_days"),
        (returns < 0).sum().alias("negative_return_days"),
        (returns == 0.0).sum().alias("zero_return_days"),
        returns.is_null().sum().alias("days_without_return"),
    )

    return pl.concat([totals, days_per_asset], how="horizontal_extend")
