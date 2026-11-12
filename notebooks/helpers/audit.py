import polars as pl
from helpers.frames import record_frame
from helpers.jumps import jump_rows
from helpers.params import load_params

CHEAP_PRICE = 1.0


def longest_unchanged_runs(valid: pl.DataFrame) -> pl.DataFrame:
    """Find the longest run of identical daily prices of each asset.

    Returns:
        One row per asset with the longest run length.

    """
    run_id = pl.col("price").rle_id().over("name").alias("run_id")
    runs = valid.sort("name", "date").with_columns(run_id).group_by("name", "run_id").agg(pl.len().alias("length"))

    return runs.group_by("name").agg(pl.col("length").max().alias("longest_run"))


def unchanged_daily_share(valid: pl.DataFrame) -> float:
    """Find the share of daily prices equal to the previous observed daily price.

    Returns:
        The share of unchanged days.

    """
    change = pl.col("price").diff().over("name")
    ordered = valid.sort("name", "date")

    return ordered.select((change == 0).mean()).item()


def audit_row_counts(rows: pl.DataFrame) -> pl.DataFrame:
    """Count the raw, daily, selected, and valid rows and assets.

    Returns:
        One row with the row and asset counts of each cleaning stage.

    """
    positive = rows.filter(pl.col("positive"))
    daily = positive.filter(pl.col("usable"))
    selected = rows.filter(pl.col("selected"))
    valid = rows.filter(pl.col("valid"))

    return record_frame(
        {
            "raw_rows": rows.height,
            "raw_assets": rows["name"].n_unique(),
            "snapshot_days": positive["date"].n_unique(),
            "dropped_days": positive["date"].n_unique() - daily["date"].n_unique(),
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


def audit_daily_shares(prices: pl.DataFrame) -> pl.DataFrame:
    """Measure the share of cleaned rows with each kind of value.

    Returns:
        One row with the return and source shares, the zero and capped return counts, and the missing rarity share.

    """
    returns = pl.col("return")
    cap = load_params()["clean"]["return_cap"]

    return prices.select(
        returns.is_null().mean().alias("rows_without_return_share"),
        (pl.col("composite_price").count() / pl.len()).alias("composite_price_share"),
        (pl.col("buff_price").count() / pl.len()).alias("buff_price_share"),
        (pl.col("rarity").is_null().sum() / pl.len()).alias("missing_rarity_share"),
        (returns == 0.0).sum().alias("zero_returns"),
        (returns == cap).sum().alias("capped_returns"),
    )


def audit_metrics(rows: pl.DataFrame, prices: pl.DataFrame) -> pl.DataFrame:
    """Calculate the cleaning diagnostics from the stage-tagged raw rows.

    Returns:
        One row with the cleaning diagnostics.

    """
    daily = rows.filter(pl.col("positive") & pl.col("usable"))
    valid = rows.filter(pl.col("valid"))
    mean_prices = prices.group_by("name").agg(pl.col("price").mean().alias("mean_price"))

    jumps = jump_rows(prices).select(
        pl.len().alias("daily_jumps"),
        pl.col("reversed").sum().alias("reversed_jumps"),
    )

    price_dates = daily.select(
        pl.col("date").min().alias("first_price_day"),
        pl.col("date").max().alias("last_price_day"),
    )

    cleaned_facts = prices.select(
        pl.len().alias("cleaned_rows"),
        pl.col("name").n_unique().alias("cleaned_assets"),
    )

    cheap_assets = mean_prices.select((pl.col("mean_price") < CHEAP_PRICE).sum().alias("assets_below_one"))

    return pl.concat(
        [
            audit_row_counts(rows),
            audit_stale_prices(valid),
            audit_daily_shares(prices),
            cleaned_facts,
            jumps,
            price_dates,
            cheap_assets,
        ],
        how="horizontal_extend",
    )
