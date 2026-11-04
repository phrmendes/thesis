from datetime import date, timedelta

import polars as pl
from helpers.frames import record_frame
from helpers.params import load_params

CHEAP_PRICE = 1.0

JUMP_THRESHOLD = 1.0

REVERSAL_RANGE = (0.75, 1.25)


def longest_unchanged_runs(valid: pl.DataFrame) -> pl.DataFrame:
    """Find the longest run of identical daily prices of each asset.

    Returns:
        One row per asset with the longest run length.

    """
    run_id = pl.col("price").rle_id().over("name").alias("run_id")
    runs = valid.sort("name", "date").with_columns(run_id).group_by("name", "run_id").agg(pl.len().alias("length"))

    return runs.group_by("name").agg(pl.col("length").max().alias("longest_run"))


def unchanged_daily_share(valid: pl.DataFrame) -> float:
    """Find the share of daily prices equal to the previous daily price.

    Returns:
        The share of unchanged days.

    """
    change = pl.col("price").diff().over("name")
    ordered = valid.sort("name", "date")

    return ordered.select((change == 0).mean()).item()


def weekly_jumps(weekly: pl.DataFrame) -> pl.DataFrame:
    """Find the observed weeks where the raw return jumps, and mark the jumps that revert.

    Returns:
        One row per jump with a `reversed` flag.

    """
    next_price = pl.col("price").shift(-1).over("name")
    previous_price = pl.col("price").shift(1).over("name")
    is_jump = (pl.col("observed") == 1) & (pl.col("raw_return").abs() > JUMP_THRESHOLD)
    low, high = REVERSAL_RANGE
    is_reversed = (next_price / previous_price).is_between(low, high).alias("reversed")

    return weekly.filter(is_jump).with_columns(is_reversed)


def assets_ending_early(audit_rows: pl.DataFrame) -> int:
    """Count the assets whose last valid week is older than the stale limit.

    Returns:
        The number of assets.

    Raises:
        TypeError: The audit frame has no last week.

    """
    last_week = audit_rows.filter(pl.col("positive"))["week"].max()

    if not isinstance(last_week, date):
        message = "the audit frame has no last week"
        raise TypeError(message)

    cutoff = last_week - timedelta(weeks=load_params()["clean"]["max_stale_weeks"])
    last_valid_week = audit_rows.filter(pl.col("valid")).group_by("name").agg(pl.col("week").max().alias("last_week"))

    return last_valid_week.filter(pl.col("last_week") < cutoff).height


def audit_row_counts(rows: pl.DataFrame) -> pl.DataFrame:
    """Count the raw, daily, selected, and valid rows and assets.

    Returns:
        One row with the row and asset counts of each cleaning stage.

    """
    daily = rows.filter(pl.col("positive"))
    selected = rows.filter(pl.col("selected"))
    valid = rows.filter(pl.col("valid"))

    return record_frame(
        {
            "raw_rows": rows.height,
            "raw_assets": rows["name"].n_unique(),
            "daily_rows": daily.height,
            "daily_assets": daily["name"].n_unique(),
            "selected_assets": selected["name"].n_unique(),
            "selected_daily_rows": selected.height,
            "valid_rows": valid.height,
            "bounds_removed_rows": selected.height - valid.height,
            "valid_assets": valid["name"].n_unique(),
        }
    )


def audit_stale_prices(valid: pl.DataFrame) -> pl.DataFrame:
    """Measure the runs of identical daily prices.

    Returns:
        One row with the unchanged share, the longest run, and the count of assets over the run limit.

    """
    max_days = load_params()["clean"]["max_unchanged_days"]
    longest_run = pl.col("longest_run")

    runs = longest_unchanged_runs(valid).select(
        longest_run.max().alias("longest_unchanged_run"),
        (longest_run > max_days).sum().alias(f"assets_with_run_over_{max_days}_days"),
    )

    share = record_frame({"unchanged_daily_share": unchanged_daily_share(valid)})

    return pl.concat([share, runs], how="horizontal_extend")


def audit_weekly_shares(weekly: pl.DataFrame) -> pl.DataFrame:
    """Measure the share of weekly rows with each kind of value.

    Returns:
        One row with the coverage shares, the zero and capped return counts, and the missing rarity share.

    """
    returns = pl.col("return")

    return weekly.select(
        (pl.col("observed").sum() / pl.len()).alias("observed_share"),
        (pl.col("composite_close").count() / pl.len()).alias("composite_close_share"),
        (pl.col("buff_close").count() / pl.len()).alias("buff_close_share"),
        ((pl.col("active_days") > 0).sum() / pl.len()).alias("steam_24h_share"),
        (pl.col("rarity").is_null().sum() / pl.len()).alias("missing_rarity_share"),
        (returns == 0.0).sum().alias("zero_returns"),
        (returns.abs() == 1.0).sum().alias("capped_returns"),
    )


def audit_metrics(rows: pl.DataFrame, prices: pl.DataFrame) -> pl.DataFrame:
    """Calculate the cleaning diagnostics from the stage-tagged raw rows.

    Returns:
        One row with the cleaning diagnostics.

    """
    daily = rows.filter(pl.col("positive"))
    valid = rows.filter(pl.col("valid"))
    mean_prices = prices.group_by("name").agg(pl.col("price").mean().alias("mean_price"))
    observed = prices.filter(pl.col("observed") == 1)

    jumps = weekly_jumps(prices).select(
        pl.len().alias("weekly_jumps"),
        pl.col("reversed").sum().alias("reversed_jumps"),
    )

    price_dates = daily.select(
        pl.col("week").min().alias("first_price_week"),
        pl.col("date").max().alias("last_price_day"),
    )

    weekly_facts = prices.select(
        pl.len().alias("weekly_rows"),
        pl.col("name").n_unique().alias("weekly_assets"),
        pl.col("week").min().alias("first_week"),
    )

    last_observed_week = observed.select(pl.col("week").max().alias("last_observed_week"))
    cheap_assets = mean_prices.select((pl.col("mean_price") < CHEAP_PRICE).sum().alias("assets_below_one"))
    ending_early = record_frame({"assets_ending_early": assets_ending_early(rows)})

    return pl.concat(
        [
            audit_row_counts(rows),
            audit_stale_prices(valid),
            audit_weekly_shares(prices),
            weekly_facts,
            jumps,
            ending_early,
            price_dates,
            cheap_assets,
            last_observed_week,
        ],
        how="horizontal_extend",
    )
