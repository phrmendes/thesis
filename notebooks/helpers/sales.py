from datetime import date, timedelta
from operator import itemgetter
from typing import TYPE_CHECKING

import polars as pl
from helpers.market import get_market_series
from helpers.parameters import parameters
from helpers.statistics import calculate_hac_lags
from numpy import column_stack, eye
from statsmodels.api import OLS, add_constant

if TYPE_CHECKING:
    from statsmodels.regression.linear_model import RegressionResultsWrapper

PHASES = ("none", "pre", "fh", "sh", "post")

PHASE_TYPE = pl.Enum(PHASES)

PHASE_RANK = {"pre": 1, "post": 2, "fh": 3, "sh": 3}

TERMS = ("const", "pre", "fh", "sh", "post", "turn_of_year")

SENSITIVITY_LAGS = tuple(parameters().calendar_effects.sensitivity_lags)

DAY = timedelta(days=1)


def keep_strongest_label(labels: dict[date, str], day: date, label: str) -> None:
    """Store a label unless the day already has a stronger one.

    A sale day beats a post day, and a post day beats a pre day.
    """
    current = labels.get(day)

    if current is None or PHASE_RANK[label] > PHASE_RANK[current]:
        labels[day] = label


def build_sale_labels(shift_days: int = 0) -> dict[date, str]:
    """Label the days before, during, and after each sale period, as Glaus (2022) does.

    The pre-sale period is half the sale length. The post-sale period is the sale length.
    The first half of the sale takes the extra day when the length is odd.
    The shift moves the whole calendar by whole days.

    Returns:
        The label of each day that belongs to a sale.

    """
    labels: dict[date, str] = {}

    for period in parameters().calendar_effects.sale_periods:
        start = date.fromisoformat(period.start)
        end = date.fromisoformat(period.end)
        length = (end - start).days + 1
        first_half = (length + 1) // 2

        for offset in range(-(length // 2), 2 * length):
            day = start + (offset + shift_days) * DAY

            if offset < 0:
                phase = "pre"
            elif offset < first_half:
                phase = "fh"
            elif offset < length:
                phase = "sh"
            else:
                phase = "post"

            keep_strongest_label(labels, day, phase)

    return labels


def format_month_day(day: date) -> str:
    """Write a day as month and day, so the text order follows the calendar order.

    Returns:
        The text `MM-DD`.

    """
    return f"{day.month:02d}-{day.day:02d}"


def is_turn_of_year(day: date) -> bool:
    """Check whether a day is in the turn of the year. The period starts in December and ends in January.

    Returns:
        True when the day is inside the period.

    """
    calendar_parameters = parameters().calendar_effects

    return (
        format_month_day(day) >= calendar_parameters.turn_of_year_start
        or format_month_day(day) <= calendar_parameters.turn_of_year_end
    )


def build_sale_calendar(days: list[date], shift_days: int = 0) -> pl.DataFrame:
    """Build the sale phase and the turn-of-the-year flag of each day.

    Returns:
        One row per day.

    """
    labels = build_sale_labels(shift_days)

    schema = {
        "date": pl.Date(),
        "phase": PHASE_TYPE,
        "turn_of_year": pl.Boolean(),
    }

    rows = {
        "date": days,
        "phase": [labels.get(day, "none") for day in days],
        "turn_of_year": [is_turn_of_year(day) for day in days],
    }

    return pl.DataFrame(rows, schema=schema)


def add_sale_calendar(market: pl.DataFrame, shift_days: int | None = None) -> pl.DataFrame:
    """Add the sale calendar to the daily market series. The shift defaults to `calendar_effects.sale_lag_days`.

    Returns:
        The market series with the phase and the turn-of-the-year flag.

    """
    shift = parameters().calendar_effects.sale_lag_days if shift_days is None else shift_days
    days: list[date] = market["date"].to_list()

    return market.join(build_sale_calendar(days, shift), on="date", how="left")


def summarize_sale_phases(prices: pl.DataFrame, shift_days: int | None = None) -> pl.DataFrame:
    """Summarize the daily item returns of each sale phase.

    The phases follow the sale calendar of the regression. The shift defaults to `calendar_effects.sale_lag_days`.

    Returns:
        One row per phase with the item-day count and the return statistics.

    """
    shift = parameters().calendar_effects.sale_lag_days if shift_days is None else shift_days
    days: list[date] = prices["date"].unique().to_list()
    calendar = build_sale_calendar(days, shift).select("date", "phase")
    returns = pl.col("return")

    return (
        prices.drop_nulls("return")
        .join(calendar, on="date")
        .group_by("phase")
        .agg(
            pl.len().alias("item_days"),
            returns.mean().alias("mean_return"),
            returns.median().alias("median_return"),
            returns.std().alias("std_return"),
            (returns > 0).mean().alias("positive_share"),
        )
        .sort("phase")
    )


def fit_phase_model(data: pl.DataFrame, column: str, lags: int | None = None) -> RegressionResultsWrapper:
    """Regress one series on the phase dummies and the turn-of-the-year dummy, with Newey-West errors.

    The bandwidth follows the sample-size rule reported by Wooldridge unless a lag count overrides it.

    Returns:
        The fitted model. Its terms follow `TERMS`.

    """
    sample = data.drop_nulls(column)
    lags = calculate_hac_lags(sample.height) if lags is None else lags
    dummies = [(sample["phase"] == phase).cast(pl.Float64).to_numpy() for phase in PHASES[1:]]
    dummies.append(sample["turn_of_year"].cast(pl.Float64).to_numpy())
    exog = add_constant(column_stack(dummies), has_constant="add")

    return OLS(sample[column].to_numpy(), exog).fit(cov_type="HAC", cov_kwds={"maxlags": lags})


def fit_phase_regression(data: pl.DataFrame, column: str, prefix: str) -> pl.DataFrame:
    """Regress one market return on the phase dummies and the turn-of-the-year dummy, with Newey-West errors.

    Returns:
        One row per term with the coefficient, the t statistic, and the p-value.

    """
    fit = fit_phase_model(data, column)

    return pl.DataFrame(
        {
            "term": list(TERMS),
            f"{prefix}_coefficient": [float(value) for value in fit.params],
            f"{prefix}_statistic": [float(value) for value in fit.tvalues],
            f"{prefix}_p_value": [float(value) for value in fit.pvalues],
        }
    )


def count_phase_days(data: pl.DataFrame) -> list[int]:
    """Count the days behind each regression term.

    Returns:
        The days of the baseline, of each phase, and of the turn of the year.

    """
    baseline = data.filter((pl.col("phase") == "none") & ~pl.col("turn_of_year")).height
    phases = [data.filter(pl.col("phase") == phase).height for phase in PHASES[1:]]

    return [baseline, *phases, data.filter(pl.col("turn_of_year")).height]


def fit_sale_regression(market: pl.DataFrame, shift_days: int | None = None) -> pl.DataFrame:
    """Compare the market return of the pre-sale, sale, and post-sale days with the other days.

    The comparison uses the equal-weight and the price-weighted market return.
    The estimates describe an association. They do not isolate a cause.

    Returns:
        One row per term with the days and the coefficients of both weightings.

    """
    data = add_sale_calendar(market, shift_days)
    equal = fit_phase_regression(data, "return", "equal")
    weighted = fit_phase_regression(data, "weighted_return", "weighted").drop("term")
    days = pl.DataFrame({"days": count_phase_days(data)})

    return pl.concat([equal.select("term"), days, equal.drop("term"), weighted], how="horizontal")


def summarize_phase_lag_sensitivity(
    data: pl.DataFrame, columns: dict[str, str], lags: tuple[int, ...] = SENSITIVITY_LAGS
) -> pl.DataFrame:
    """Refit the phase regression with each Newey-West lag count and keep the p-value of two phases.

    The lag count changes the standard errors. It does not change the coefficients.

    Returns:
        One row per lag count with the p-value of the first-half and of the post-sale term for each series.

    """
    rows = []

    for lag in lags:
        row: dict[str, float] = {"lags": lag}

        for name, column in columns.items():
            model = fit_phase_model(data, column, lag)
            row[f"{name}_fh_p_value"] = float(model.pvalues[TERMS.index("fh")])
            row[f"{name}_post_p_value"] = float(model.pvalues[TERMS.index("post")])

        rows.append(row)

    return pl.DataFrame(rows)


def partition_segments(prices: pl.DataFrame, segment: pl.Expr, min_items: int) -> list[tuple[str, int, pl.DataFrame]]:
    """Split the prices by segment and keep the segments with enough items.

    Returns:
        The name, the item count, and the prices of each segment, from the largest.

    """
    parts = [
        (str(part["segment"][0]), part["name"].n_unique(), part)
        for part in prices.with_columns(segment.alias("segment")).partition_by("segment")
    ]

    return sorted((part for part in parts if part[1] >= min_items), key=itemgetter(1), reverse=True)


def fit_segment_models(prices: pl.DataFrame, segment: pl.Expr, min_items: int) -> dict[str, RegressionResultsWrapper]:
    """Fit the phase regression of the equal-weight market return in each segment of items.

    Returns:
        One fitted model per segment with at least `min_items` items, from the largest.

    """
    return {
        name: fit_phase_model(add_sale_calendar(get_market_series(part)), "return")
        for name, _, part in partition_segments(prices, segment, min_items)
    }


def estimate_segment_phase_effects(prices: pl.DataFrame, segment: pl.Expr, min_items: int) -> pl.DataFrame:
    """Estimate the first-half and post-sale effects of the market return in each segment of items.

    Returns:
        One row per segment with at least `min_items` items, from the largest.

    """
    rows = []

    for name, items, part in partition_segments(prices, segment, min_items):
        terms = fit_phase_regression(add_sale_calendar(get_market_series(part)), "return", "equal")
        first_half = terms.filter(pl.col("term") == "fh").row(0, named=True)
        post_sale = terms.filter(pl.col("term") == "post").row(0, named=True)
        rows.append(
            {
                "segment": name,
                "items": items,
                "fh_coefficient": first_half["equal_coefficient"],
                "fh_statistic": first_half["equal_statistic"],
                "fh_p_value": first_half["equal_p_value"],
                "post_coefficient": post_sale["equal_coefficient"],
                "post_statistic": post_sale["equal_statistic"],
                "post_p_value": post_sale["equal_p_value"],
            }
        )

    return pl.DataFrame(rows)


def fit_weekday_model(data: pl.DataFrame, column: str, lags: int | None = None) -> RegressionResultsWrapper:
    """Fit the market return on seven weekday dummies without a constant, with Newey-West errors.

    The bandwidth follows the sample-size rule reported by Wooldridge unless a lag count overrides it.

    Returns:
        The fitted model. Its coefficients are the mean return of each weekday.

    """
    sample = data.drop_nulls(column)
    lags = calculate_hac_lags(sample.height) if lags is None else lags
    weekday = sample["date"].dt.weekday()
    dummies = column_stack([(weekday == day).cast(pl.Float64).to_numpy() for day in range(1, 8)])

    return OLS(sample[column].to_numpy(), dummies).fit(cov_type="HAC", cov_kwds={"maxlags": lags})


def estimate_weekday_effects(market: pl.DataFrame) -> pl.DataFrame:
    """Estimate the mean market return of each weekday, for the equal-weight and the price-weighted return.

    Returns:
        One row per weekday, from Monday, with the mean, the t statistic, and the p-value of both weightings.

    """
    equal = fit_weekday_model(market, "return")
    weighted = fit_weekday_model(market, "weighted_return")

    return pl.DataFrame(
        {
            "weekday": list(range(1, 8)),
            "equal_coefficient": [float(value) for value in equal.params],
            "equal_statistic": [float(value) for value in equal.tvalues],
            "equal_p_value": [float(value) for value in equal.pvalues],
            "weighted_coefficient": [float(value) for value in weighted.params],
            "weighted_statistic": [float(value) for value in weighted.tvalues],
            "weighted_p_value": [float(value) for value in weighted.pvalues],
        }
    )


def run_weekday_test(market: pl.DataFrame, lags: int | None = None) -> pl.DataFrame:
    """Test that the seven weekday means are equal, with a Wald test on the Newey-West covariance.

    Returns:
        One row with the p-value of each weighting.

    """
    contrasts = eye(7)[:-1] - eye(7)[1:]
    equal = fit_weekday_model(market, "return", lags).wald_test(contrasts, scalar=True)
    weighted = fit_weekday_model(market, "weighted_return", lags).wald_test(contrasts, scalar=True)

    return pl.DataFrame({"equal_p_value": [float(equal.pvalue)], "weighted_p_value": [float(weighted.pvalue)]})


def summarize_weekday_lag_sensitivity(market: pl.DataFrame, lags: tuple[int, ...] = SENSITIVITY_LAGS) -> pl.DataFrame:
    """Refit the weekday test with each Newey-West lag count.

    Returns:
        One row per lag count with the p-value of each weighting.

    """
    rows = [{"lags": lag, **run_weekday_test(market, lag).row(0, named=True)} for lag in lags]

    return pl.DataFrame(rows)
