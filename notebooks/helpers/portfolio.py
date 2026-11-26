from datetime import date, timedelta
from typing import TYPE_CHECKING, Literal

import polars as pl
from helpers.parameters import parameters
from helpers.segments import NO_RARITY, build_rarity_segment
from helpers.statistics import calculate_ratio
from numpy import asarray, float64, median
from numpy.random import default_rng

if TYPE_CHECKING:
    from numpy.typing import NDArray

RARITY_LEVELS = {
    "Default": 0,
    "Base Grade": 1,
    "Consumer Grade": 1,
    "Highlight Base Grade": 1,
    "Industrial Grade": 2,
    "Distinguished": 3,
    "High Grade": 3,
    "Mil-Spec Grade": 3,
    "Exceptional": 4,
    "Remarkable": 4,
    "Restricted": 4,
    "Classified": 5,
    "Exotic": 5,
    "Superior": 5,
    "Covert": 6,
    "Extraordinary": 6,
    "Master": 6,
    "Contraband": 7,
}

HoldingPeriod = Literal["validation", "testing"]


def get_price_window(window: int | None) -> int:
    """Choose the number of last observed prices that smooth a price. The default is `portfolios.price_window_days`.

    Returns:
        The window in observed prices.

    """
    return parameters().portfolios.price_window_days if window is None else window


def find_first_holding_day(prices: pl.DataFrame, holding_period: HoldingPeriod) -> date:
    """Find the first date in the requested holding period.

    Returns:
        The first holding date.

    Raises:
        ValueError: The input has no dates for the holding period.
        TypeError: The holding dates do not use the Date type.

    """
    day = prices.filter(pl.col("period") == holding_period)["date"].min()

    match day:
        case None:
            message = f"prices have no {holding_period} dates. Run thesis data clean before this analysis."
            raise ValueError(message)
        case date():
            return day
        case _:
            message = "holding dates must use the Date type"
            raise TypeError(message)


def calculate_entry_prices(
    prices: pl.DataFrame, window: int | None = None, *, holding_period: HoldingPeriod = "testing"
) -> pl.DataFrame:
    """Calculate entry prices from observations strictly before the holding period.

    Returns:
        One median entry price per asset with a recent observed price.

    """
    max_stale_days = parameters().portfolios.max_stale_days
    first_day = find_first_holding_day(prices, holding_period)
    recent = pl.col("date").is_between(first_day - timedelta(days=max_stale_days), first_day, closed="left")
    entry_price = pl.col("price").tail(get_price_window(window)).median().alias("entry_price")

    return prices.filter(recent).sort("name", "date").group_by("name", maintain_order=True).agg(entry_price)


def calculate_exit_prices(
    prices: pl.DataFrame, window: int | None = None, *, holding_period: HoldingPeriod = "testing"
) -> pl.DataFrame:
    """Calculate median exit prices within the holding period.

    Returns:
        One exit price per asset with an observed holding-period price.

    """
    exit_price = pl.col("price").tail(get_price_window(window)).median().alias("exit_price")
    holding = prices.filter(pl.col("period") == holding_period).sort("name", "date")

    return holding.group_by("name").agg(exit_price)


def select_candidates(
    prices: pl.DataFrame, window: int | None = None, *, holding_period: HoldingPeriod = "testing"
) -> pl.DataFrame:
    """Summarize each candidate using only history before the holding period.

    Validation uses training history. Testing uses training and validation history.

    Returns:
        One row of historical price, return, and risk measures per buyable asset.

    """
    size = get_price_window(window)
    first_day = find_first_holding_day(prices, holding_period)
    is_historical = pl.col("date") < first_day
    returns = pl.col("return")
    candidates = (
        prices.filter(is_historical)
        .sort("name", "date")
        .join(
            calculate_entry_prices(prices, window, holding_period=holding_period).select("name"), on="name", how="inner"
        )
    )

    return candidates.group_by("name").agg(
        pl.col("price").head(size).median().alias("initial_price"),
        pl.col("price").tail(size).median().alias("final_price"),
        returns.mean().alias("mean_return"),
        returns.std().alias("return_stddev"),
        returns.filter(returns < 0).std().alias("negative_std"),
    )


def add_selection_ratios(candidates: pl.DataFrame) -> pl.DataFrame:
    """Add historical ROI, Sharpe, and Sortino ratios for asset selection.

    Returns:
        The candidates with the three ratio columns.

    """
    net_sale_share = parameters().portfolios.net_sale_share
    net_final_price = pl.col("final_price") * net_sale_share
    roi = (net_final_price / pl.col("initial_price") - 1).alias("roi")
    sharpe = calculate_ratio(pl.col("mean_return"), pl.col("return_stddev")).alias("sharpe")
    sortino = calculate_ratio(pl.col("mean_return"), pl.col("negative_std")).alias("sortino")

    return candidates.with_columns(roi, sharpe, sortino)


def build_threshold_tests(thresholds: dict[str, float]) -> dict[str, pl.Expr]:
    """Build the test of each training minimum. A null ratio fails the test.

    Returns:
        One boolean expression for ROI, Sharpe, and Sortino.

    """
    return {name: (pl.col(name) >= thresholds[name]).fill_null(value=False) for name in ("roi", "sharpe", "sortino")}


def check_thresholds(thresholds: dict[str, float]) -> pl.Expr:
    """Build the test of the three training minimums together.

    Returns:
        The boolean expression.

    """
    tests = build_threshold_tests(thresholds)

    return tests["roi"] & tests["sharpe"] & tests["sortino"]


def count_threshold_passes(candidates: pl.DataFrame, thresholds: dict[str, float]) -> pl.DataFrame:
    """Count the candidates that pass each training minimum and all three.

    Returns:
        One row with the candidates and the count for ROI, Sharpe, Sortino, and all three.

    """
    tests = build_threshold_tests(thresholds)

    return add_selection_ratios(candidates).select(
        pl.len().alias("candidates"),
        *[test.sum().alias(name) for name, test in tests.items()],
        check_thresholds(thresholds).sum().alias("all"),
    )


def summarize_portfolio_rarity(candidates: pl.DataFrame, selected: pl.DataFrame, prices: pl.DataFrame) -> pl.DataFrame:
    """Compare the rarity of the selected assets with the rarity of all candidates.

    Returns:
        One row per rarity, in level order with alphabetical ties and missing rarity last, plus counts and shares.

    """
    labels = prices.select("name", build_rarity_segment()).unique("name")

    def calculate_rarity_share(assets: pl.DataFrame, prefix: str) -> pl.DataFrame:
        count = pl.col(f"{prefix}_assets")
        counts = assets.join(labels, on="name").group_by("rarity").agg(pl.len().alias(f"{prefix}_assets"))

        return counts.with_columns((count / count.sum()).alias(f"{prefix}_share"))

    shares = calculate_rarity_share(candidates, "candidate").join(
        calculate_rarity_share(selected, "selected"), on="rarity", how="left"
    )

    is_missing_rarity = pl.col("rarity") == NO_RARITY
    rarity_level = pl.col("rarity").replace_strict(RARITY_LEVELS, default=len(RARITY_LEVELS))

    return shares.fill_null(0).sort([is_missing_rarity, rarity_level, "rarity"])


def select_eligible_assets(
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
    ranked = (
        add_selection_ratios(candidates)
        .filter(check_thresholds(thresholds))
        .sort([rank, "name"], descending=[True, False])
    )

    if ranked.height < k:
        message = f"requested K value {k} exceeds eligible asset count {ranked.height}"
        raise ValueError(message)

    return ranked.head(k)


def calculate_position_weights(holding_prices: pl.DataFrame, entries: pl.DataFrame, count: int) -> pl.DataFrame:
    """Give each selected asset an equal initial weight and follow its price from its entry price.

    Returns:
        One row per asset and testing day with a price, with the weight.

    """
    weight = (pl.col("price") / pl.col("entry_price") / count).alias("weight")
    selected = holding_prices.join(entries, on="name", how="inner").sort("name", "date")

    return selected.with_columns(weight)


def build_position_values(
    prices: pl.DataFrame,
    names: pl.DataFrame,
    count: int,
    window: int | None = None,
    *,
    holding_period: HoldingPeriod = "testing",
) -> pl.DataFrame:
    """Value each selected position in validation or testing with equal initial weights.

    An asset keeps its last observed weight through every day without a price.
    Before its first holding-period price an asset keeps its entry weight.
    On the last day an asset takes its smoothed exit price.
    The carried weight only values the position. It never makes a return.

    Returns:
        One row per asset and holding day with its contribution to the portfolio value.

    """
    holding = prices.filter(pl.col("period") == holding_period)
    days = holding.select("date").unique()
    last_day = days["date"].max()
    entries = calculate_entry_prices(prices, window, holding_period=holding_period).join(names, on="name", how="inner")
    weights = calculate_position_weights(holding, entries, count).select("name", "date", "weight")
    carried_weight = pl.col("weight").fill_null(strategy="forward").over("name").fill_null(1 / count)
    exit_weight = pl.col("exit_price") / pl.col("entry_price") / count
    takes_exit = pl.col("exit_price").is_not_null() & (pl.col("date") == last_day)
    positions = (
        names.join(days, how="cross")
        .join(entries, on="name")
        .join(calculate_exit_prices(prices, window, holding_period=holding_period), on="name", how="left")
        .join(weights, on=["name", "date"], how="left")
        .sort("name", "date")
        .with_columns(carried_weight)
        .with_columns(pl.when(takes_exit).then(exit_weight).otherwise(pl.col("weight")).alias("weight"))
    )

    return positions.select("name", "date", pl.col("weight").alias("value"))


def build_hold_positions(
    prices: pl.DataFrame,
    names: pl.DataFrame,
    count: int,
    window: int | None = None,
    *,
    holding_period: HoldingPeriod = "testing",
) -> pl.DataFrame:
    """Aggregate the asset positions into the daily buy-and-hold portfolio value.

    Returns:
        One row per holding day with the portfolio value.

    """
    positions = build_position_values(prices, names, count, window, holding_period=holding_period)

    return positions.group_by("date").agg(pl.col("value").sum()).sort("date")


def calculate_daily_returns(values: pl.DataFrame) -> pl.DataFrame:
    """Calculate the capped daily return of the portfolio value.

    The portfolio starts at one on the entry day, so the first holding day has a return too.
    The final-sale fee applies once, on the last day.

    Returns:
        The values with a `return` column.

    """
    net_sale_share = parameters().portfolios.net_sale_share
    cap = parameters().clean.return_cap
    is_last_day = pl.col("date") == pl.col("date").max()
    growth = pl.col("value") / pl.col("value").shift(1).fill_null(1.0)
    sale_growth = growth * net_sale_share
    gross_return = pl.when(is_last_day).then(sale_growth - 1).otherwise(growth - 1)

    return values.sort("date").with_columns(gross_return.clip(-cap, cap).alias("return"))


def calculate_portfolio_returns(values: pl.DataFrame) -> pl.DataFrame:
    """Turn the daily portfolio values into capped returns and daily ratios.

    Returns:
        One row per day with the value, the return, and the portfolio ROI, Sharpe and Sortino.

    Raises:
        ValueError: The portfolio has no holding days.

    """
    if values.is_empty():
        message = "portfolio has no holding days"
        raise ValueError(message)

    net_sale_share = parameters().portfolios.net_sale_share
    returns = calculate_daily_returns(values)
    roi = net_sale_share * values["value"][-1] - 1
    daily = pl.col("return")
    sharpe = calculate_ratio(daily.mean(), daily.std()).alias("sharpe")
    sortino = calculate_ratio(daily.mean(), daily.filter(daily < 0).std()).alias("sortino")

    return returns.with_columns(pl.lit(roi).alias("roi"), sharpe, sortino).select(
        "date", "value", "return", "roi", "sharpe", "sortino"
    )


def summarize_portfolio(rows: pl.DataFrame, assets: int) -> pl.DataFrame:
    """Summarize the portfolio ratios. They are daily.

    Returns:
        One row with the assets, the days, the sale fee in percent, and the ratios.

    """
    net_sale_share = parameters().portfolios.net_sale_share

    return rows.select(
        pl.lit(assets).alias("assets"),
        pl.len().alias("days"),
        pl.lit((1 - net_sale_share) * 100).alias("sale_fee"),
        pl.col("roi").first(),
        pl.col("sharpe").first(),
        pl.col("sortino").first(),
    )


def calculate_asset_multiples(prices: pl.DataFrame, window: int | None = None) -> pl.DataFrame:
    """Find the gross multiple of each buyable asset: its exit price over its entry price.

    An asset with no testing price keeps its entry value, so its multiple is one.

    Returns:
        One row per buyable asset with the entry price, the exit price, and the multiple.

    """
    multiple = (pl.col("exit_price") / pl.col("entry_price")).fill_null(1.0).alias("multiple")

    return (
        calculate_entry_prices(prices, window)
        .join(calculate_exit_prices(prices, window), on="name", how="left")
        .with_columns(multiple)
    )


def calculate_buy_and_hold_roi(multiples: NDArray[float64]) -> float:
    """Calculate the net ROI of an equal-weight buy-and-hold portfolio from the multiples of its assets.

    Returns:
        The ROI after the final-sale fee.

    """
    net_sale_share = parameters().portfolios.net_sale_share

    return float(net_sale_share * multiples.mean() - 1)


def simulate_random_portfolios(values: pl.DataFrame, size: int, draws: int, seed: int) -> pl.DataFrame:
    """Draw equal-weight portfolios and calculate their net ROI, daily volatility, and daily Sharpe.

    Returns:
        One row per draw with sample volatility and Sharpe from the common daily-return rules.

    """
    rng = default_rng(seed)
    paths = values.drop("date").to_numpy()
    rows = []
    volatility = pl.col("return").std().alias("volatility")

    for _draw in range(draws):
        indices = rng.choice(paths.shape[1], size=size, replace=False)
        portfolio_values = pl.DataFrame({"date": values["date"], "value": paths[:, indices].mean(axis=1)})
        returns = calculate_portfolio_returns(portfolio_values)
        rows.append(returns.select(pl.col("roi").first(), volatility, pl.col("sharpe").first()))

    return pl.concat(rows)


def build_random_benchmark_row(
    label: str, selected_roi_value: float, selected_sharpe: float | None, metrics: pl.DataFrame
) -> pl.DataFrame:
    """Summarize random portfolio returns, daily risk, and the selected portfolio percentiles.

    Returns:
        One row with ROI summaries, mean daily volatility and Sharpe, and the selected ROI and Sharpe percentiles.

    """
    roi = pl.col("roi")
    sharpe = pl.col("sharpe")
    selected_roi_percentile = (roi <= selected_roi_value).mean().alias("selected_percentile")
    selected_sharpe_percentile = (
        (sharpe <= pl.lit(selected_sharpe, dtype=pl.Float64)).mean().alias("selected_sharpe_percentile")
    )

    return metrics.select(
        pl.lit(label).alias("portfolio"),
        roi.mean(),
        roi.quantile(0.05, interpolation="linear").alias("p05"),
        roi.quantile(0.95, interpolation="linear").alias("p95"),
        selected_roi_percentile,
        pl.col("volatility").mean(),
        sharpe.mean(),
        selected_sharpe_percentile,
    )


def summarize_benchmarks(
    prices: pl.DataFrame,
    multiples: pl.DataFrame,
    eligible: pl.DataFrame,
    selected: pl.DataFrame,
) -> pl.DataFrame:
    """Compare the selected portfolio with all candidates, all eligible assets, and random portfolios.

    Returns:
        One row per benchmark with its ROI. Random rows add daily risk and the selected ROI and Sharpe percentiles.

    """
    portfolio_parameters = parameters().portfolios
    by_name = multiples.select("name", "multiple")
    selected_multiples = selected.select("name").join(by_name, on="name")["multiple"].to_numpy()
    eligible_by_name = eligible.select("name").join(by_name, on="name")
    eligible_multiples = eligible_by_name["multiple"].to_numpy()
    candidate_multiples = by_name["multiple"].to_numpy()
    selected_value = calculate_buy_and_hold_roi(selected_multiples)
    size = selected.height
    paths = (
        build_position_values(prices, by_name.select("name"), 1)
        .pivot(on="name", index="date", values="value")
        .sort("date")
    )
    selected_returns = calculate_portfolio_returns(build_hold_positions(prices, selected.select("name"), size))
    selected_sharpe = selected_returns["sharpe"][0]
    eligible_paths = paths.select("date", *eligible_by_name["name"].to_list())
    candidate_paths = paths.select("date", *by_name["name"].to_list())

    single = pl.DataFrame(
        {
            "portfolio": ["selected", "candidates", "eligible", "median_candidate"],
            "roi": [
                selected_value,
                calculate_buy_and_hold_roi(candidate_multiples),
                calculate_buy_and_hold_roi(eligible_multiples),
                calculate_buy_and_hold_roi(asarray(median(candidate_multiples))),
            ],
        }
    )

    random_rows = pl.concat(
        [
            build_random_benchmark_row(
                "random_eligible",
                selected_value,
                selected_sharpe,
                simulate_random_portfolios(
                    eligible_paths, size, portfolio_parameters.random_draws, portfolio_parameters.seed
                ),
            ),
            build_random_benchmark_row(
                "random_candidates",
                selected_value,
                selected_sharpe,
                simulate_random_portfolios(
                    candidate_paths, size, portfolio_parameters.random_draws, portfolio_parameters.seed
                ),
            ),
        ]
    )

    return pl.concat([single, random_rows], how="diagonal")


def summarize_k_sweep(
    prices: pl.DataFrame,
    candidates: pl.DataFrame,
    rank: str,
    thresholds: dict[str, float],
    *,
    holding_period: HoldingPeriod = "validation",
) -> pl.DataFrame:
    """Evaluate feasible portfolio sizes in the requested holding period.

    Returns:
        One row per feasible size with net ROI and daily Sharpe and Sortino ratios.

    Raises:
        ValueError: No configured size fits the eligible universe.

    """
    rows = []
    eligible_count = add_selection_ratios(candidates).filter(check_thresholds(thresholds)).height

    for size in parameters().portfolios.k_sweep:
        if size > eligible_count:
            continue

        selected = select_eligible_assets(candidates, size, rank, thresholds)
        values = build_hold_positions(prices, selected.select("name"), size, holding_period=holding_period)
        rows.append(summarize_portfolio(calculate_portfolio_returns(values), size))

    if not rows:
        message = "no configured portfolio size fits the eligible universe"
        raise ValueError(message)

    return pl.concat(rows).select("assets", "roi", "sharpe", "sortino")


def select_portfolio_size(summary: pl.DataFrame, roi_tolerance: float) -> int:
    """Maximize daily Sharpe within the allowed net ROI sacrifice, with smaller sizes first in ties.

    Returns:
        The selected asset count.

    Raises:
        ValueError: No size has finite ROI and Sharpe values.

    """
    roi = pl.col("roi").cast(pl.Float64)
    sharpe = pl.col("sharpe").cast(pl.Float64)
    is_finite = roi.is_finite() & sharpe.is_finite()
    feasible = summary.filter(is_finite)

    if feasible.is_empty():
        message = "no portfolio size has finite ROI and Sharpe values"
        raise ValueError(message)

    best_roi = float(feasible.select(roi.max()).item())
    is_near_best = roi >= best_roi - roi_tolerance
    ranked = feasible.filter(is_near_best).sort(["sharpe", "assets"], descending=[True, False])

    return int(ranked["assets"][0])


def calculate_selected_roi(
    prices: pl.DataFrame, size: int, thresholds: dict[str, float], window: int | None = None
) -> float | None:
    """Select assets by historical ROI and calculate the net buy-and-hold ROI.

    Returns:
        The net ROI, or None when fewer than size assets meet the thresholds.

    """
    candidates = select_candidates(prices, window)
    eligible_count = count_threshold_passes(candidates, thresholds)["all"].item()

    if eligible_count < size:
        return None

    selected = select_eligible_assets(candidates, size, "roi", thresholds)
    rows = calculate_portfolio_returns(build_hold_positions(prices, selected.select("name"), size, window))

    return float(rows["roi"][0])


def build_benchmark_paths(prices: pl.DataFrame, groups: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Follow the daily value of equal-weight buy-and-hold portfolios, one for each named group of assets.

    The value starts at one on the entry day and has no sale fee.

    Returns:
        One row per portfolio and testing day with the value.

    """
    paths = []

    for label, names in groups.items():
        values = build_hold_positions(prices, names.select("name"), names.height)
        paths.append(values.with_columns(pl.lit(label).alias("portfolio")))

    return pl.concat(paths).select("portfolio", "date", "value")


def calculate_item_contributions(selected: pl.DataFrame, multiples: pl.DataFrame, prices: pl.DataFrame) -> pl.DataFrame:
    """Break the portfolio ROI down by item: the multiple of each item and its contribution to the gross return.

    Returns:
        One row per selected item, from the largest contribution.

    """
    rarity = prices.select("name", build_rarity_segment()).unique("name")
    contribution = ((pl.col("multiple") - 1) / selected.height).alias("contribution")
    selection_roi = selected.select("name", "roi")

    return (
        selection_roi.join(multiples.select("name", "entry_price", "exit_price", "multiple"), on="name")
        .join(rarity, on="name")
        .with_columns(contribution)
        .sort("contribution", descending=True)
    )
