import polars as pl
from helpers.frames import bucket_label, with_empty_buckets

SHARE_BUCKET_LABELS = ("≤ 20%", "20-40%", "40-60%", "60-80%", "> 80%")

SHARE_BUCKET_BREAKS = (0.2, 0.4, 0.6, 0.8)


def activity_summary(prices: pl.DataFrame) -> pl.DataFrame:
    """Group the items by the share of days with a Steam 24-hour price between their first and last day.

    Returns:
        One row per bucket with the item count.

    """
    span_days = (pl.col("date").max() - pl.col("date").min()).dt.total_days() + 1
    observed_share = (pl.len() / span_days).alias("observed_share")
    shares = prices.group_by("name").agg(observed_share)
    share_bucket = bucket_label("observed_share", SHARE_BUCKET_BREAKS, SHARE_BUCKET_LABELS).alias("share_bucket")
    counts = shares.group_by(share_bucket).agg(pl.len().alias("items"))

    return with_empty_buckets(counts, "share_bucket", SHARE_BUCKET_LABELS)
