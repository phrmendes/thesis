import polars as pl
from helpers.params import load_params
from helpers.statistics import ratio


def buyable_names(prices: pl.DataFrame) -> pl.DataFrame:
    """Find the assets with a price in the first testing week.

    Returns:
        One row per buyable asset name.

    """
    testing = prices.filter(pl.col("period") == "testing")
    first_testing_week = testing["week"].min()

    return testing.filter(pl.col("week") == first_testing_week).select("name")


def training_candidates(prices: pl.DataFrame) -> pl.DataFrame:
    """Summarize the training weeks of every asset with a price in the first testing week.

    Returns:
        One row per asset with the training price, return and risk values.

    """
    returns = pl.col("return")
    training = prices.sort("name", "week").filter(pl.col("period") == "training")
    candidates = training.join(buyable_names(prices), on="name", how="inner")

    return candidates.group_by("name").agg(
        pl.col("price").first().alias("initial_price"),
        pl.col("price").last().alias("final_price"),
        returns.mean().alias("mean_return"),
        returns.std().alias("return_stddev"),
        returns.filter(returns < 0).std().alias("negative_std"),
    )


def with_training_ratios(candidates: pl.DataFrame) -> pl.DataFrame:
    """Add the training ROI, Sharpe, and Sortino ratios.

    Returns:
        The candidates with the three ratio columns.

    """
    net_sale_share = load_params()["portfolio"]["net_sale_share"]
    net_final_price = pl.col("final_price") * net_sale_share
    roi = (net_final_price / pl.col("initial_price") - 1).alias("roi")
    sharpe = ratio(pl.col("mean_return"), pl.col("return_stddev")).alias("sharpe")
    sortino = ratio(pl.col("mean_return"), pl.col("negative_std")).alias("sortino")

    return candidates.with_columns(roi, sharpe, sortino)


def eligible_assets(
    candidates: pl.DataFrame,
    k: int,
    rank: str,
    thresholds: dict[str, float],
) -> pl.DataFrame:
    """Keep the assets above the thresholds and take the best k by the rank column.

    Returns:
        The k best assets in descending order of the rank column.

    Raises:
        ValueError: The count of eligible assets is below k.

    """
    meets_thresholds = (
        (pl.col("roi") >= thresholds["roi"])
        & (pl.col("sharpe") >= thresholds["sharpe"])
        & (pl.col("sortino") >= thresholds["sortino"])
    )
    ranked = with_training_ratios(candidates).filter(meets_thresholds).sort(rank, descending=True)

    if ranked.height < k:
        message = f"requested K value {k} exceeds eligible asset count {ranked.height}"
        raise ValueError(message)

    return ranked.head(k)


def position_weights(testing: pl.DataFrame, names: pl.DataFrame, count: int) -> pl.DataFrame:
    """Give each selected asset an equal initial weight and follow its price.

    Returns:
        One row per asset and testing week with the weight.

    """
    initial_price = pl.col("price").first().over("name")
    weight = (pl.col("price") / initial_price / count).alias("weight")
    selected = testing.join(names, on="name", how="inner").sort("name", "week")

    return selected.with_columns(weight)


def carried_weights(positions: pl.DataFrame, weeks: pl.DataFrame) -> pl.DataFrame:
    """Keep the last weight of each asset that stops before the last testing week.

    Returns:
        One row per week with the carried weight.

    """
    last_week = pl.col("week").max().alias("last_week")
    last_weight = pl.col("weight").last().alias("last_weight")
    stopped = positions.group_by("name").agg(last_week, last_weight)
    carried = stopped.join(weeks, how="cross").filter(pl.col("last_week") < pl.col("week"))

    return carried.group_by("week").agg(pl.col("last_weight").sum().alias("carried_weight"))


def hold_positions(prices: pl.DataFrame, names: pl.DataFrame, count: int) -> pl.DataFrame:
    """Hold the selected assets in the testing weeks with equal initial weights.

    An asset that stops keeps its last weight until the last testing week.

    Returns:
        One row per testing week with the portfolio value.

    """
    testing = prices.filter(pl.col("period") == "testing")
    weeks = testing.select("week").unique()
    positions = position_weights(testing, names, count)
    held = positions.group_by("week").agg(pl.col("weight").sum().alias("held_weight"))
    carried = carried_weights(positions, weeks)
    value = (pl.col("held_weight").fill_null(0.0) + pl.col("carried_weight").fill_null(0.0)).alias("value")
    joined = weeks.join(held, on="week", how="left").join(carried, on="week", how="left")

    return joined.select("week", value).sort("week")


def weekly_returns(values: pl.DataFrame) -> pl.DataFrame:
    """Calculate the capped weekly return of the portfolio value.

    The final-sale fee applies once, in the last week.

    Returns:
        The values with a `return` column.

    """
    params = load_params()
    net_sale_share = params["portfolio"]["net_sale_share"]
    cap = params["clean"]["return_cap"]
    is_last_week = pl.col("week") == pl.col("week").max()
    growth = pl.col("value") / pl.col("value").shift(1)
    sale_growth = growth * net_sale_share
    gross_return = pl.when(is_last_week).then(sale_growth - 1).otherwise(growth - 1)

    return values.sort("week").with_columns(gross_return.clip(-cap, cap).alias("return"))


def portfolio_returns(values: pl.DataFrame) -> pl.DataFrame:
    """Turn the weekly portfolio values into capped returns and weekly ratios.

    Returns:
        One row per week with the value, the return, and the portfolio ROI, Sharpe and Sortino.

    Raises:
        ValueError: The portfolio has no testing weeks.

    """
    if values.is_empty():
        message = "portfolio has no testing weeks"
        raise ValueError(message)

    net_sale_share = load_params()["portfolio"]["net_sale_share"]
    returns = weekly_returns(values)
    roi = net_sale_share * values["value"][-1] / values["value"][0] - 1
    weekly = pl.col("return")
    sharpe = ratio(weekly.mean(), weekly.std()).alias("sharpe")
    sortino = ratio(weekly.mean(), weekly.filter(weekly < 0).std()).alias("sortino")

    return returns.with_columns(pl.lit(roi).alias("roi"), sharpe, sortino).select(
        "week", "value", "return", "roi", "sharpe", "sortino"
    )


def portfolio_summary(rows: pl.DataFrame, assets: int) -> pl.DataFrame:
    """Summarize the portfolio ratios. They are weekly.

    Returns:
        One row with the assets, the weeks, the sale fee in percent, and the ratios.

    """
    net_sale_share = load_params()["portfolio"]["net_sale_share"]

    return rows.select(
        pl.lit(assets).alias("assets"),
        pl.len().alias("weeks"),
        pl.lit((1 - net_sale_share) * 100).alias("sale_fee"),
        pl.col("roi").first(),
        pl.col("sharpe").first(),
        pl.col("sortino").first(),
    )
