import polars as pl
from helpers.frames import add_empty_buckets, build_bucket_label
from helpers.parameters import parameters

SHARE_BUCKET_LABELS = tuple(parameters().data_quality.share_bucket_labels)

SHARE_BUCKET_BREAKS = tuple(parameters().data_quality.share_bucket_breaks)


def summarize_activity(prices: pl.DataFrame) -> pl.DataFrame:
    """Group the items by the share of days with a Steam 24-hour price between their first and last day.

    Returns:
        One row per bucket with the item count.

    """
    span_days = (pl.col("date").max() - pl.col("date").min()).dt.total_days() + 1
    observed_share = (pl.len() / span_days).alias("observed_share")
    share_bucket = build_bucket_label("observed_share", SHARE_BUCKET_BREAKS, SHARE_BUCKET_LABELS).alias("share_bucket")
    counts = prices.group_by("name").agg(observed_share).group_by(share_bucket).agg(pl.len().alias("items"))

    return add_empty_buckets(counts, "share_bucket", SHARE_BUCKET_LABELS)
