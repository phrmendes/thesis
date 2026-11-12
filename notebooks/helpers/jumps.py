import polars as pl

UP_JUMP = 1.0

DOWN_JUMP = -0.5

REVERSAL_RANGE = (0.75, 1.25)

DIRECTION_TYPE = pl.Enum(["up", "down"])


def jump_rows(prices: pl.DataFrame) -> pl.DataFrame:
    """Find the days where the price at least doubles or at least halves, and mark the jumps that revert.

    A jump reverts when the next observed price is within `REVERSAL_RANGE` of the price before the jump.

    Returns:
        One row per jump with its direction and a `reversed` flag.

    """
    ordered = prices.sort("name", "date")
    next_price = pl.col("price").shift(-1).over("name")
    previous_price = pl.col("price").shift(1).over("name")
    is_up = pl.col("raw_return") > UP_JUMP
    is_down = pl.col("raw_return") < DOWN_JUMP
    low, high = REVERSAL_RANGE
    is_reversed = (next_price / previous_price).is_between(low, high).alias("reversed")
    direction = pl.when(is_up).then(pl.lit("up")).otherwise(pl.lit("down")).cast(DIRECTION_TYPE).alias("direction")

    return ordered.with_columns(is_reversed).filter(is_up | is_down).with_columns(direction)


def jump_summary(prices: pl.DataFrame) -> pl.DataFrame:
    """Summarize the jumps of each direction: count, share that reverts, median size, and share in training.

    Returns:
        One row per direction.

    """
    size = pl.col("raw_return").abs()

    return (
        jump_rows(prices)
        .group_by("direction")
        .agg(
            pl.len().alias("jumps"),
            pl.col("reversed").mean().alias("reversed_share"),
            size.median().alias("median_size"),
            (pl.col("period") == "training").mean().alias("training_share"),
        )
        .sort("direction")
    )


def jump_days(prices: pl.DataFrame, top: int) -> pl.DataFrame:
    """Find the days with the most jumps and the share of the items that jumped.

    Returns:
        One row per day, from the day with the most jumps.

    """
    jumps = jump_rows(prices).group_by("date").agg(pl.len().alias("jumps"))
    items = prices.drop_nulls("return").group_by("date").agg(pl.len().alias("items"))
    share = (pl.col("jumps") / pl.col("items")).alias("jump_share")

    return jumps.join(items, on="date").with_columns(share).sort("jumps", descending=True).head(top)
