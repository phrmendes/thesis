from datetime import date, timedelta
from typing import TYPE_CHECKING

import polars as pl
from helpers.params import load_params
from helpers.segments import rarity_segment
from helpers.statistics import ratio
from numpy import asarray, float64, median, percentile
from numpy.random import default_rng

if TYPE_CHECKING:
    from numpy.typing import NDArray


def price_window(window: int | None) -> int:
    """Choose the number of last observed prices that smooth a price. The default is `portfolio.price_window_days`.

    Returns:
        The window in observed prices.

    """
    return load_params()["portfolio"]["price_window_days"] if window is None else window


def first_testing_day(prices: pl.DataFrame) -> date:
    """Find the first testing day.

    Returns:
        The day.

    Raises:
        TypeError: The prices have no testing day.

    """
    day = prices.filter(pl.col("period") == "testing")["date"].min()

    if not isinstance(day, date):
        message = "the prices have no testing day"
        raise TypeError(message)

    return day


def entry_prices(prices: pl.DataFrame, window: int | None = None) -> pl.DataFrame:
    """Find the entry price of each asset: the median of its last observed prices up to the first testing day.

    A price must be at most `max_stale_days` old, so every candidate had a price when the testing days began.

    Returns:
        One row per buyable asset with its entry price.

    """
    max_stale_days = load_params()["portfolio"]["max_stale_days"]
    last_day = first_testing_day(prices)
    recent = pl.col("date").is_between(last_day - timedelta(days=max_stale_days), last_day)
    entry_price = pl.col("price").tail(price_window(window)).median().alias("entry_price")

    return prices.filter(recent).sort("name", "date").group_by("name", maintain_order=True).agg(entry_price)


def exit_prices(prices: pl.DataFrame, window: int | None = None) -> pl.DataFrame:
    """Find the exit price of each asset: the median of its last observed prices in the testing days.

    Returns:
        One row per asset with a testing price and its exit price.

    """
    exit_price = pl.col("price").tail(price_window(window)).median().alias("exit_price")
    testing = prices.filter(pl.col("period") == "testing").sort("name", "date")

    return testing.group_by("name").agg(exit_price)


def training_candidates(prices: pl.DataFrame, window: int | None = None) -> pl.DataFrame:
    """Summarize the training days of every buyable asset.

    The initial and final prices are medians of the first and the last observed training prices.

    Returns:
        One row per asset with the training price, return and risk values.

    """
    size = price_window(window)
    returns = pl.col("return")
    training = prices.sort("name", "date").filter(pl.col("period") == "training")
    candidates = training.join(entry_prices(prices, window).select("name"), on="name", how="inner")

    return candidates.group_by("name").agg(
        pl.col("price").head(size).median().alias("initial_price"),
        pl.col("price").tail(size).median().alias("final_price"),
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


def threshold_tests(thresholds: dict[str, float]) -> dict[str, pl.Expr]:
    """Build the test of each training minimum. A null ratio fails the test.

    Returns:
        One boolean expression for ROI, Sharpe, and Sortino.

    """
    return {name: (pl.col(name) >= thresholds[name]).fill_null(value=False) for name in ("roi", "sharpe", "sortino")}


def meets_thresholds(thresholds: dict[str, float]) -> pl.Expr:
    """Build the test of the three training minimums together.

    Returns:
        The boolean expression.

    """
    tests = threshold_tests(thresholds)

    return tests["roi"] & tests["sharpe"] & tests["sortino"]


def threshold_pass_counts(candidates: pl.DataFrame, thresholds: dict[str, float]) -> pl.DataFrame:
    """Count the candidates that pass each training minimum and all three.

    Returns:
        One row with the candidates and the count for ROI, Sharpe, Sortino, and all three.

    """
    tests = threshold_tests(thresholds)

    return with_training_ratios(candidates).select(
        pl.len().alias("candidates"),
        *[test.sum().alias(name) for name, test in tests.items()],
        meets_thresholds(thresholds).sum().alias("all"),
    )


def portfolio_rarity(candidates: pl.DataFrame, selected: pl.DataFrame, prices: pl.DataFrame) -> pl.DataFrame:
    """Compare the rarity of the selected assets with the rarity of all candidates.

    Returns:
        One row per rarity with the candidate and the selected counts and shares.

    """
    labels = prices.select("name", rarity_segment()).unique("name")

    def rarity_share(assets: pl.DataFrame, prefix: str) -> pl.DataFrame:
        count = pl.col(f"{prefix}_assets")
        counts = assets.join(labels, on="name").group_by("rarity").agg(pl.len().alias(f"{prefix}_assets"))

        return counts.with_columns((count / count.sum()).alias(f"{prefix}_share"))

    shares = rarity_share(candidates, "candidate").join(rarity_share(selected, "selected"), on="rarity", how="left")

    return shares.fill_null(0).sort("candidate_assets", descending=True)


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
    ranked = with_training_ratios(candidates).filter(meets_thresholds(thresholds)).sort(rank, descending=True)

    if ranked.height < k:
        message = f"requested K value {k} exceeds eligible asset count {ranked.height}"
        raise ValueError(message)

    return ranked.head(k)


def position_weights(testing: pl.DataFrame, entries: pl.DataFrame, count: int) -> pl.DataFrame:
    """Give each selected asset an equal initial weight and follow its price from its entry price.

    Returns:
        One row per asset and testing day with a price, with the weight.

    """
    weight = (pl.col("price") / pl.col("entry_price") / count).alias("weight")
    selected = testing.join(entries, on="name", how="inner").sort("name", "date")

    return selected.with_columns(weight)


def hold_positions(prices: pl.DataFrame, names: pl.DataFrame, count: int, window: int | None = None) -> pl.DataFrame:
    """Hold the selected assets in the testing days with equal initial weights.

    An asset keeps its last observed weight through every day without a price.
    Before its first testing price an asset keeps its entry weight.
    On the last day an asset takes its smoothed exit price.
    The carried weight only values the position. It never makes a return.

    Returns:
        One row per testing day with the portfolio value.

    """
    testing = prices.filter(pl.col("period") == "testing")
    days = testing.select("date").unique()
    last_day = days["date"].max()
    entries = entry_prices(prices, window).join(names, on="name", how="inner")
    weights = position_weights(testing, entries, count).select("name", "date", "weight")
    carried_weight = pl.col("weight").fill_null(strategy="forward").over("name").fill_null(1 / count)
    exit_weight = pl.col("exit_price") / pl.col("entry_price") / count
    takes_exit = pl.col("exit_price").is_not_null() & (pl.col("date") == last_day)
    grid = (
        names.join(days, how="cross").join(entries, on="name").join(exit_prices(prices, window), on="name", how="left")
    )
    held = grid.join(weights, on=["name", "date"], how="left").sort("name", "date").with_columns(carried_weight)
    final = held.with_columns(pl.when(takes_exit).then(exit_weight).otherwise(pl.col("weight")).alias("weight"))

    return final.group_by("date").agg(pl.col("weight").sum().alias("value")).sort("date")


def daily_returns(values: pl.DataFrame) -> pl.DataFrame:
    """Calculate the capped daily return of the portfolio value.

    The portfolio starts at the value one on the entry day, so the first testing day has a return too.
    The final-sale fee applies once, on the last day.

    Returns:
        The values with a `return` column.

    """
    params = load_params()
    net_sale_share = params["portfolio"]["net_sale_share"]
    cap = params["clean"]["return_cap"]
    is_last_day = pl.col("date") == pl.col("date").max()
    growth = pl.col("value") / pl.col("value").shift(1).fill_null(1.0)
    sale_growth = growth * net_sale_share
    gross_return = pl.when(is_last_day).then(sale_growth - 1).otherwise(growth - 1)

    return values.sort("date").with_columns(gross_return.clip(-cap, cap).alias("return"))


def portfolio_returns(values: pl.DataFrame) -> pl.DataFrame:
    """Turn the daily portfolio values into capped returns and daily ratios.

    Returns:
        One row per day with the value, the return, and the portfolio ROI, Sharpe and Sortino.

    Raises:
        ValueError: The portfolio has no testing days.

    """
    if values.is_empty():
        message = "portfolio has no testing days"
        raise ValueError(message)

    net_sale_share = load_params()["portfolio"]["net_sale_share"]
    returns = daily_returns(values)
    roi = net_sale_share * values["value"][-1] - 1
    daily = pl.col("return")
    sharpe = ratio(daily.mean(), daily.std()).alias("sharpe")
    sortino = ratio(daily.mean(), daily.filter(daily < 0).std()).alias("sortino")

    return returns.with_columns(pl.lit(roi).alias("roi"), sharpe, sortino).select(
        "date", "value", "return", "roi", "sharpe", "sortino"
    )


def portfolio_summary(rows: pl.DataFrame, assets: int) -> pl.DataFrame:
    """Summarize the portfolio ratios. They are daily.

    Returns:
        One row with the assets, the days, the sale fee in percent, and the ratios.

    """
    net_sale_share = load_params()["portfolio"]["net_sale_share"]

    return rows.select(
        pl.lit(assets).alias("assets"),
        pl.len().alias("days"),
        pl.lit((1 - net_sale_share) * 100).alias("sale_fee"),
        pl.col("roi").first(),
        pl.col("sharpe").first(),
        pl.col("sortino").first(),
    )


def asset_multiples(prices: pl.DataFrame, window: int | None = None) -> pl.DataFrame:
    """Find the gross multiple of each buyable asset: its exit price over its entry price.

    An asset with no testing price keeps its entry value, so its multiple is one.

    Returns:
        One row per buyable asset with the entry price, the exit price, and the multiple.

    """
    multiple = (pl.col("exit_price") / pl.col("entry_price")).fill_null(1.0).alias("multiple")

    return entry_prices(prices, window).join(exit_prices(prices, window), on="name", how="left").with_columns(multiple)


def buy_and_hold_roi(multiples: NDArray[float64]) -> float:
    """Calculate the net ROI of an equal-weight buy-and-hold portfolio from the multiples of its assets.

    Returns:
        The ROI after the final-sale fee.

    """
    net_sale_share = load_params()["portfolio"]["net_sale_share"]

    return float(net_sale_share * multiples.mean() - 1)


def random_portfolio_rois(multiples: NDArray[float64], size: int, draws: int, seed: int) -> NDArray[float64]:
    """Draw random equal-weight portfolios of `size` assets without replacement and calculate their ROI.

    Returns:
        The ROI of each draw.

    """
    rng = default_rng(seed)
    net_sale_share = load_params()["portfolio"]["net_sale_share"]
    draw_means = [rng.choice(multiples, size=size, replace=False).mean() for _ in range(draws)]

    return asarray(draw_means) * net_sale_share - 1


def random_benchmark_row(label: str, selected_roi_value: float, rois: NDArray[float64]) -> pl.DataFrame:
    """Summarize the ROI of random portfolios and the percentile of the selected portfolio among them.

    Returns:
        One row with the mean ROI, the 5th and 95th percentiles, and the percentile of the selected ROI.

    """
    return pl.DataFrame(
        {
            "portfolio": [label],
            "roi": [float(rois.mean())],
            "p05": [float(percentile(rois, 5))],
            "p95": [float(percentile(rois, 95))],
            "selected_percentile": [float((rois <= selected_roi_value).mean())],
        }
    )


def benchmark_summary(
    multiples: pl.DataFrame,
    eligible: pl.DataFrame,
    selected: pl.DataFrame,
) -> pl.DataFrame:
    """Compare the selected portfolio with all candidates, all eligible assets, and random portfolios.

    Returns:
        One row per benchmark with its ROI. The random rows add the percentiles and the selected percentile.

    """
    params = load_params()["portfolio"]
    by_name = multiples.select("name", "multiple")
    selected_multiples = selected.select("name").join(by_name, on="name")["multiple"].to_numpy()
    eligible_multiples = eligible.select("name").join(by_name, on="name")["multiple"].to_numpy()
    candidate_multiples = by_name["multiple"].to_numpy()
    selected_value = buy_and_hold_roi(selected_multiples)
    size = selected.height
    draws, seed = params["random_draws"], params["seed"]

    single = pl.DataFrame(
        {
            "portfolio": ["selected", "candidates", "eligible", "median_candidate"],
            "roi": [
                selected_value,
                buy_and_hold_roi(candidate_multiples),
                buy_and_hold_roi(eligible_multiples),
                buy_and_hold_roi(asarray(median(candidate_multiples))),
            ],
        }
    )

    random_rows = pl.concat(
        [
            random_benchmark_row(
                "random_eligible", selected_value, random_portfolio_rois(eligible_multiples, size, draws, seed)
            ),
            random_benchmark_row(
                "random_candidates", selected_value, random_portfolio_rois(candidate_multiples, size, draws, seed)
            ),
        ]
    )

    return pl.concat([single, random_rows], how="diagonal")


def k_sweep_summary(
    prices: pl.DataFrame,
    candidates: pl.DataFrame,
    rank: str,
    thresholds: dict[str, float],
) -> pl.DataFrame:
    """Run the buy-and-hold portfolio for each size of the k sweep.

    Returns:
        One row per size with the ROI, Sharpe, and Sortino.

    """
    rows = []

    for size in load_params()["portfolio"]["k_sweep"]:
        selected = eligible_assets(candidates, size, rank, thresholds)
        values = hold_positions(prices, selected.select("name"), size)
        rows.append(portfolio_summary(portfolio_returns(values), size))

    return pl.concat(rows).select("assets", "roi", "sharpe", "sortino")


def selected_roi(prices: pl.DataFrame, size: int, thresholds: dict[str, float], window: int | None = None) -> float:
    """Select the top assets by training ROI and calculate the ROI of their buy-and-hold portfolio.

    Returns:
        The net ROI.

    """
    candidates = training_candidates(prices, window)
    selected = eligible_assets(candidates, size, "roi", thresholds)
    rows = portfolio_returns(hold_positions(prices, selected.select("name"), size, window))

    return float(rows["roi"][0])


def benchmark_paths(prices: pl.DataFrame, groups: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Follow the daily value of equal-weight buy-and-hold portfolios, one for each named group of assets.

    The value starts at one on the entry day and has no sale fee.

    Returns:
        One row per portfolio and testing day with the value.

    """
    paths = []

    for label, names in groups.items():
        values = hold_positions(prices, names.select("name"), names.height)
        paths.append(values.with_columns(pl.lit(label).alias("portfolio")))

    return pl.concat(paths).select("portfolio", "date", "value")


def item_contributions(selected: pl.DataFrame, multiples: pl.DataFrame, prices: pl.DataFrame) -> pl.DataFrame:
    """Break the portfolio ROI down by item: the multiple of each item and its contribution to the gross return.

    Returns:
        One row per selected item, from the largest contribution.

    """
    rarity = prices.select("name", rarity_segment()).unique("name")
    contribution = ((pl.col("multiple") - 1) / selected.height).alias("contribution")
    training_roi = selected.select("name", "roi")

    return (
        training_roi.join(multiples.select("name", "entry_price", "exit_price", "multiple"), on="name")
        .join(rarity, on="name")
        .with_columns(contribution)
        .sort("contribution", descending=True)
    )
