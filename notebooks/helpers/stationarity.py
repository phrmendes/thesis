import polars as pl
from helpers.statistics import adf_test

SIGNIFICANCE = 0.05

MAX_LAG = 7


def adf_p_value(values: list[float]) -> float:
    """Run an ADF test with a fixed lag limit, so thousands of items stay fast.

    Returns:
        The p-value.

    """
    return adf_test(values, MAX_LAG)[1]


def item_stationarity(prices: pl.DataFrame, min_days: int) -> pl.DataFrame:
    """Test the log price and the daily return of each item for a unit root.

    The observed days of an item form the series. A gap in the days is not filled.

    Returns:
        One row with the item count. Each series has the share of items that reject a unit root and the median p.

    """
    ordered = prices.sort("name", "date")
    price_p_values: list[float] = []
    return_p_values: list[float] = []

    for item in ordered.partition_by("name"):
        returns: list[float] = item["return"].drop_nulls().to_list()

        if len(returns) < min_days:
            continue

        price_p_values.append(adf_p_value(item["price"].log().to_list()))
        return_p_values.append(adf_p_value(returns))

    p_values = pl.DataFrame({"price": price_p_values, "return": return_p_values})

    return p_values.select(
        pl.len().alias("items"),
        (pl.col("price") < SIGNIFICANCE).mean().alias("price_reject_share"),
        pl.col("price").median().alias("price_median_p_value"),
        (pl.col("return") < SIGNIFICANCE).mean().alias("return_reject_share"),
        pl.col("return").median().alias("return_median_p_value"),
    )
