import polars as pl
from helpers.schemas import PERIODS


def summarize_evaluation_split(prices: pl.DataFrame) -> pl.DataFrame:
    """Summarize the chronological training, validation, and testing periods.

    Returns:
        One row with date bounds, distinct date counts, and item-day counts for each period.

    """
    summaries = []

    for period in PERIODS:
        is_period = pl.col("period") == period
        dates = pl.col("date").filter(is_period)
        summaries.extend(
            [
                dates.min().alias(f"{period}_start"),
                dates.max().alias(f"{period}_end"),
                dates.n_unique().alias(f"{period}_days"),
                dates.len().alias(f"{period}_records"),
            ]
        )

    return prices.select(summaries)
