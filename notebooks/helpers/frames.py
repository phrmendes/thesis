from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from datetime import date


def record_frame(record: dict[str, float | date | None]) -> pl.DataFrame:
    """Build a one-row frame whose columns keep the raw value types.

    Returns:
        The frame with one column per name.

    """
    return pl.DataFrame({name: [value] for name, value in record.items()})


def bucket_label(column: str, breaks: tuple[float, ...], labels: tuple[str, ...]) -> pl.Expr:
    """Label each value of one column with the bucket that holds it.

    Returns:
        The expression with the bucket label as an enum in the bucket order.

    """
    return pl.col(column).cut(list(breaks), labels=list(labels))


def with_empty_buckets(counts: pl.DataFrame, key: str, labels: tuple[str, ...]) -> pl.DataFrame:
    """Add a zero row for each bucket that has no count, in the bucket order.

    Returns:
        One row per bucket label. The key is an enum in the bucket order.

    """
    all_buckets = pl.DataFrame({key: pl.Series(key, list(labels), dtype=pl.Enum(list(labels)))})

    return all_buckets.join(counts, on=key, how="left", maintain_order="left").fill_null(0)
