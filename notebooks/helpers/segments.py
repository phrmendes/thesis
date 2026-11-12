import polars as pl
from helpers.frames import bucket_label
from helpers.sources import EXPENSIVE_PRICE

PRICE_BUCKET_LABELS = ("≤ 5", "5-25", "25-100", "100-800", "> 800")

PRICE_BUCKET_BREAKS = (5, 25, 100, EXPENSIVE_PRICE)

NO_RARITY = "Sem raridade"


def rarity_segment() -> pl.Expr:
    """Name the rarity of each row, with a label for a missing rarity.

    Returns:
        The rarity as text.

    """
    return pl.col("rarity").cast(pl.String).fill_null(NO_RARITY)


def price_segment() -> pl.Expr:
    """Label each row with its daily price bucket in USD.

    Returns:
        The bucket label as an enum in the bucket order.

    """
    return bucket_label("price", PRICE_BUCKET_BREAKS, PRICE_BUCKET_LABELS)


def segment_summary(prices: pl.DataFrame, segment: pl.Expr) -> pl.DataFrame:
    """Summarize the daily item returns of each segment.

    Returns:
        One row per segment, from the lowest to the highest median price.

    """
    returns = pl.col("return")

    return (
        prices.group_by(segment.alias("segment"))
        .agg(
            pl.col("name").n_unique().alias("items"),
            pl.len().alias("item_days"),
            pl.col("price").median().alias("median_price"),
            returns.mean().alias("mean_return"),
            returns.std().alias("std_return"),
            (returns == 0.0).mean().alias("zero_share"),
        )
        .sort("median_price")
    )
