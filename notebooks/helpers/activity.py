import polars as pl
from helpers.frames import bucket_label, with_empty_buckets

ACTIVE_BUCKET_LABELS = ("0", "1-2", "3-4", "5-6", "7")

ACTIVE_BUCKET_BREAKS = (0, 2, 4, 6)


def activity_summary(prices: pl.DataFrame) -> pl.DataFrame:
    """Group the item-weeks by the number of days with a Steam 24-hour price.

    Returns:
        One row per bucket with the item-week count.

    """
    active_bucket = bucket_label("active_days", ACTIVE_BUCKET_BREAKS, ACTIVE_BUCKET_LABELS).alias("active_bucket")
    counts = prices.group_by(active_bucket).agg(pl.len().alias("item_weeks"))

    return with_empty_buckets(counts, "active_bucket", ACTIVE_BUCKET_LABELS)
