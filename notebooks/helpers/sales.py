from datetime import date, timedelta
from typing import TYPE_CHECKING, NamedTuple

import polars as pl
from helpers.market import market_series
from helpers.params import load_params
from numpy import column_stack, eye
from statsmodels.api import OLS, add_constant

if TYPE_CHECKING:
    from statsmodels.regression.linear_model import RegressionResultsWrapper

PHASES = ("none", "pre", "fh", "sh", "post")

PHASE_TYPE = pl.Enum(PHASES)

PHASE_RANK = {"pre": 1, "post": 2, "fh": 3, "sh": 3}

TERMS = ("const", "pre", "fh", "sh", "post", "turn_of_year")

HAC_LAGS = 7

DAY = timedelta(days=1)


class SaleLabel(NamedTuple):
    """The phase of one day and the sale that owns it."""

    phase: str
    year: int
    season: str


def keep_strongest(labels: dict[date, SaleLabel], day: date, label: SaleLabel) -> None:
    """Store a label unless the day already has a stronger one.

    A sale day beats a post day, and a post day beats a pre day.
    """
    current = labels.get(day)

    if current is None or PHASE_RANK[label.phase] > PHASE_RANK[current.phase]:
        labels[day] = label


def sale_labels(shift_days: int = 0) -> dict[date, SaleLabel]:
    """Label the days before, during, and after each sale period, as Glaus (2022) does.

    The pre-sale period is half the sale length. The post-sale period is the sale length.
    The first half of the sale takes the extra day when the length is odd.
    The shift moves the whole calendar by whole days.

    Returns:
        The label of each day that belongs to a sale.

    """
    labels: dict[date, SaleLabel] = {}

    for period in load_params()["sale_periods"]:
        start = date.fromisoformat(period["start"])
        end = date.fromisoformat(period["end"])
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

            keep_strongest(labels, day, SaleLabel(phase, start.year, period["season"]))

    return labels


def month_day(day: date) -> str:
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
    eda = load_params()["eda"]

    return month_day(day) >= eda["turn_of_year_start"] or month_day(day) <= eda["turn_of_year_end"]


def sale_calendar(days: list[date], shift_days: int = 0) -> pl.DataFrame:
    """Build the sale phase, the sale year and season, and the turn-of-the-year flag of each day.

    Returns:
        One row per day.

    """
    labels = sale_labels(shift_days)
    none = SaleLabel("none", 0, "")

    schema = {
        "date": pl.Date(),
        "phase": PHASE_TYPE,
        "event_year": pl.Int32(),
        "event_season": pl.String(),
        "turn_of_year": pl.Boolean(),
    }

    rows = {
        "date": days,
        "phase": [labels.get(day, none).phase for day in days],
        "event_year": [labels.get(day, none).year or None for day in days],
        "event_season": [labels.get(day, none).season or None for day in days],
        "turn_of_year": [is_turn_of_year(day) for day in days],
    }

    return pl.DataFrame(rows, schema=schema)


def with_sale_calendar(market: pl.DataFrame, shift_days: int | None = None) -> pl.DataFrame:
    """Add the sale calendar to the daily market series. The shift defaults to `eda.sale_lag_days`.

    Returns:
        The market series with the phase, the event, and the turn-of-the-year flag.

    """
    shift = load_params()["eda"]["sale_lag_days"] if shift_days is None else shift_days
    days: list[date] = market["date"].to_list()

    return market.join(sale_calendar(days, shift), on="date", how="left")


def sale_season_summary(prices: pl.DataFrame) -> pl.DataFrame:
    """Summarize the daily item returns of each sale season.

    A day belongs to a season when it falls inside a Steam sale period. Other days have the season `none`.

    Returns:
        One row per season with the item-day count and the return statistics.

    """
    returns = pl.col("return")

    return (
        prices.drop_nulls("return")
        .group_by("sale_season")
        .agg(
            pl.len().alias("item_days"),
            returns.mean().alias("mean_return"),
            returns.median().alias("median_return"),
            returns.std().alias("std_return"),
            (returns > 0).mean().alias("positive_share"),
        )
        .sort("sale_season")
    )


def phase_regression(data: pl.DataFrame, column: str, prefix: str) -> pl.DataFrame:
    """Regress one market return on the phase dummies and the turn-of-the-year dummy, with Newey-West errors.

    Returns:
        One row per term with the coefficient, the t statistic, and the p-value.

    """
    sample = data.drop_nulls(column)
    dummies = [(sample["phase"] == phase).cast(pl.Float64).to_numpy() for phase in PHASES[1:]]
    dummies.append(sample["turn_of_year"].cast(pl.Float64).to_numpy())
    exog = add_constant(column_stack(dummies), has_constant="add")
    fit = OLS(sample[column].to_numpy(), exog).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})

    return pl.DataFrame(
        {
            "term": list(TERMS),
            f"{prefix}_coefficient": [float(value) for value in fit.params],
            f"{prefix}_statistic": [float(value) for value in fit.tvalues],
            f"{prefix}_p_value": [float(value) for value in fit.pvalues],
        }
    )


def phase_days(data: pl.DataFrame) -> list[int]:
    """Count the days behind each regression term.

    Returns:
        The days of the baseline, of each phase, and of the turn of the year.

    """
    baseline = data.filter((pl.col("phase") == "none") & ~pl.col("turn_of_year")).height
    phases = [data.filter(pl.col("phase") == phase).height for phase in PHASES[1:]]

    return [baseline, *phases, data.filter(pl.col("turn_of_year")).height]


def sale_regression(market: pl.DataFrame, shift_days: int | None = None) -> pl.DataFrame:
    """Compare the market return of the pre-sale, sale, and post-sale days with the other days.

    The comparison uses the equal-weight and the price-weighted market return.
    The estimates describe an association. They do not isolate a cause.

    Returns:
        One row per term with the days and the coefficients of both weightings.

    """
    data = with_sale_calendar(market, shift_days)
    equal = phase_regression(data, "market_return", "equal")
    weighted = phase_regression(data, "weighted_return", "weighted").drop("term")
    days = pl.DataFrame({"days": phase_days(data)})

    return pl.concat([equal.select("term"), days, equal.drop("term"), weighted], how="horizontal")


def sale_event_summary(market: pl.DataFrame, shift_days: int | None = None) -> pl.DataFrame:
    """Summarize the equal-weight market return around each sale event.

    Returns:
        One row per sale with its sale days and the mean return of the pre, first-half, second-half, and post days.

    """
    data = with_sale_calendar(market, shift_days).drop_nulls("event_year")
    returns = pl.col("market_return")
    is_sale = pl.col("phase").is_in(["fh", "sh"])

    def phase_mean(phase: str) -> pl.Expr:
        return returns.filter(pl.col("phase") == phase).mean().alias(f"{phase}_return")

    return (
        data.group_by("event_year", "event_season")
        .agg(
            pl.col("date").filter(is_sale).min().alias("first_sale_day"),
            is_sale.sum().alias("sale_days"),
            phase_mean("pre"),
            phase_mean("fh"),
            phase_mean("sh"),
            phase_mean("post"),
        )
        .sort("first_sale_day")
    )


def trading_activity(prices: pl.DataFrame) -> pl.DataFrame:
    """Measure the daily trading activity: the share of the items listed so far that have a 24-hour price.

    An item counts as listed from its first day with a price.

    Returns:
        One row per day with the active items, the listed items, and the share.

    """
    first_days = prices.group_by("name").agg(pl.col("date").min().alias("first_date"))
    listed = (
        first_days.group_by("first_date")
        .agg(pl.len().alias("new_items"))
        .sort("first_date")
        .with_columns(pl.col("new_items").cum_sum().alias("listed_items"))
        .rename({"first_date": "date"})
        .select("date", "listed_items")
    )
    active = prices.group_by("date").agg(pl.len().alias("active_items")).sort("date")
    share = (pl.col("active_items") / pl.col("listed_items")).alias("trading_share")

    return active.join_asof(listed, on="date").with_columns(share)


def activity_regression(prices: pl.DataFrame) -> pl.DataFrame:
    """Compare the trading activity of the sale phases with the other days, as Glaus (2022) does for volume.

    The estimates describe an association. A day with a price is a crude sign of a sale.

    Returns:
        One row per term with the days and the coefficient, t statistic, and p-value of the activity share.

    """
    data = with_sale_calendar(trading_activity(prices))
    activity = phase_regression(data, "trading_share", "activity")
    days = pl.DataFrame({"days": phase_days(data)})

    return pl.concat([activity.select("term"), days, activity.drop("term")], how="horizontal")


def segment_phase_effects(prices: pl.DataFrame, segment: pl.Expr, min_items: int) -> pl.DataFrame:
    """Estimate the first-half and post-sale effects of the market return in each segment of items.

    Returns:
        One row per segment with at least `min_items` items, from the largest.

    """
    rows = []

    for part in prices.with_columns(segment.alias("segment")).partition_by("segment"):
        items = part["name"].n_unique()

        if items < min_items:
            continue

        terms = phase_regression(with_sale_calendar(market_series(part)), "market_return", "equal")
        first_half = terms.filter(pl.col("term") == "fh").row(0, named=True)
        post_sale = terms.filter(pl.col("term") == "post").row(0, named=True)
        rows.append(
            {
                "segment": str(part["segment"][0]),
                "items": items,
                "fh_coefficient": first_half["equal_coefficient"],
                "fh_statistic": first_half["equal_statistic"],
                "post_coefficient": post_sale["equal_coefficient"],
                "post_statistic": post_sale["equal_statistic"],
            }
        )

    return pl.DataFrame(rows).sort("items", descending=True)


def weekday_fit(data: pl.DataFrame, column: str) -> RegressionResultsWrapper:
    """Fit the market return on seven weekday dummies without a constant, with Newey-West errors.

    Returns:
        The fitted model. Its coefficients are the mean return of each weekday.

    """
    sample = data.drop_nulls(column)
    weekday = sample["date"].dt.weekday()
    dummies = column_stack([(weekday == day).cast(pl.Float64).to_numpy() for day in range(1, 8)])

    return OLS(sample[column].to_numpy(), dummies).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})


def weekday_effects(market: pl.DataFrame) -> pl.DataFrame:
    """Estimate the mean market return of each weekday, for the equal-weight and the price-weighted return.

    Returns:
        One row per weekday, from Monday, with the mean and the t statistic of both weightings.

    """
    equal = weekday_fit(market, "market_return")
    weighted = weekday_fit(market, "weighted_return")

    return pl.DataFrame(
        {
            "weekday": list(range(1, 8)),
            "equal_coefficient": [float(value) for value in equal.params],
            "equal_statistic": [float(value) for value in equal.tvalues],
            "weighted_coefficient": [float(value) for value in weighted.params],
            "weighted_statistic": [float(value) for value in weighted.tvalues],
        }
    )


def weekday_joint_test(market: pl.DataFrame) -> pl.DataFrame:
    """Test that the seven weekday means are equal, with a Wald test on the Newey-West covariance.

    Returns:
        One row with the p-value of each weighting.

    """
    contrasts = eye(7)[:-1] - eye(7)[1:]
    equal = weekday_fit(market, "market_return").wald_test(contrasts, scalar=True)
    weighted = weekday_fit(market, "weighted_return").wald_test(contrasts, scalar=True)

    return pl.DataFrame({"equal_p_value": [float(equal.pvalue)], "weighted_p_value": [float(weighted.pvalue)]})
