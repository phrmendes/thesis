use ./clean.nu [clean-stages]
use ./helpers.nu [metrics-from one-row round-text]
use ./params.nu [load-params]
use ./stats.nu [count-where]

# Shift one column by one day inside each asset. Name the result previous_price.
def previous-price [column: string]: nothing -> any {
    polars col $column | polars shift 1 | polars over (polars col name) | polars as previous_price
}

# Count the longest run of identical consecutive daily prices of each asset. The 7-day average repeats when no sale changes it.
def longest-identical-runs []: any -> any {
    let valid = $in

    $valid
    | polars sort-by name date
    | polars with-column (previous-price price)
    | polars with-column (
        polars when ((polars col price) == (polars col previous_price)) 0
        | polars otherwise 1
        | polars cumulative sum
        | polars over (polars col name)
        | polars as run
    )
    | polars group-by [name run]
    | polars agg [
        (polars col price | polars count | polars as run_days)
    ]
    | polars group-by name
    | polars agg [
        (polars col run_days | polars max | polars as longest_run)
    ]
}

# Count the weekly jumps above 100% and the jumps that reverse the next week. Read the cleaned prices, so the price column is already named price.
def weekly-jumps []: any -> any {
    let prices = $in
    let is_observed = ((polars col observed) == 1)
    let is_jump = (((polars col raw_return) | polars math abs) > 1.0)

    $prices
    | polars with-column (
        polars col price
        | polars shift (-1)
        | polars over (polars col name)
        | polars as next_price
    )
    | polars with-column (previous-price price)
    | polars filter $is_observed
    | polars filter $is_jump
    | polars with-column (
        polars when (
            (((polars col next_price) / (polars col previous_price)) > 0.75)
            and (((polars col next_price) / (polars col previous_price)) < 1.25)
        ) 1
        | polars otherwise 0
        | polars as reversed
    )
}

# Count the rows, the names, the first week and the last day of one daily frame.
def daily-counts []: any -> record {
    polars select [
        (polars len | polars as rows)
        (polars col name | polars n-unique | polars as assets)
        (polars col week | polars min | polars as first_week)
        (polars col date | polars max | polars as last_day)
    ]
    | polars collect
    | polars into-nu
    | first
}

# Summarize the diagnostics of the cleaned prices in one pass.
def cleaned-counts []: any -> record {
    polars select [
        (polars len | polars as rows)
        (polars col observed | polars sum | polars as observed)
        (polars col composite_close | polars count | polars as composite_rows)
        (count-where ((polars col active_days) > 0) | polars as active_rows)
        (polars col buff_close | polars count | polars as buff_rows)
        (count-where (((polars col return)) == 0.0) | polars as zero_returns)
        (
            count-where (((polars col return) | polars math abs) == 1.0)
            | polars as capped_returns
        )
        (
            count-where ((polars col rarity | polars is-null))
            | polars as missing_rarity
        )
        (polars col week | polars min | polars as first_week)
        (polars col week | polars n-unique | polars as weeks)
    ]
    | one-row
}

# Format one count as a share of the cleaned rows, with four decimals.
def share-text [count: int, total: int]: nothing -> string {
    $count / $total | round-text 4
}

# Count the raw and cleaned stages. Run this before the raw files are removed. Weekly numbers come from the cleaned table, so the grid is not built twice.
export def cleaning-audit [stages: record, cleaned]: nothing -> table {
    let raw = $stages.raw
    let params = (load-params)

    let is_observed = ((polars col observed) == 1)
    let has_previous = ((polars col previous_price | polars is-not-null))
    let is_cheap = ((polars col mean_price) < 1.0)

    let count_columns = [
        (polars len | polars as rows)
        (polars col name | polars n-unique | polars as assets)
    ]

    let counts_raw = $raw | polars select $count_columns | one-row
    let counts_daily = $stages.daily | daily-counts
    let counts_selected = $stages.selected | polars select $count_columns | one-row
    let counts_valid = $stages.valid | polars select $count_columns | one-row
    let counts_weekly = $cleaned | polars select $count_columns | one-row
    let counts_cleaned = $cleaned | cleaned-counts

    let last_observed = (
        $cleaned
        | polars filter $is_observed
        | polars select (polars col week | polars max | polars as week)
        | one-row
        | get week
    )

    let selected_daily_rows = (
        $stages.daily
        | polars join $stages.selected name name --inner
        | polars select (polars len | polars as rows)
        | one-row
        | get rows
    )

    let unchanged_share = (
        $stages.valid
        | polars sort-by name date
        | polars with-column (previous-price price)
        | polars filter $has_previous
        | polars with-column (
            polars when ((polars col price) == (polars col previous_price)) 1.0
            | polars otherwise 0.0
            | polars as same
        )
        | polars select (polars col same | polars mean | polars as unchanged_share)
        | one-row
        | get unchanged_share
    )

    let runs = (
        $stages.valid
        | longest-identical-runs
        | polars collect
        | polars into-nu
    )

    let jumps = (
        $cleaned
        | weekly-jumps
        | polars select [
            (polars len | polars as rows)
            (polars col reversed | polars sum | polars as reversed)
        ]
        | one-row
    )

    let last_week = (
        $stages.daily
        | polars select (polars col week | polars max | polars as last_week)
        | one-row
        | get last_week
    )

    let assets_ending_early = (
        $stages.valid
        | polars group-by name
        | polars agg [(polars col week | polars max | polars as last_week)]
        | polars collect
        | polars into-nu
        | where last_week < ($last_week - ($params.clean.max_stale_weeks * 1wk))
        | length
    )

    let cheap_assets = (
        $cleaned
        | polars group-by name
        | polars agg [(polars col price | polars mean | polars as mean_price)]
        | polars filter $is_cheap
        | polars select (polars len | polars as assets)
        | one-row
        | get assets
    )

    let total = $counts_cleaned.rows

    {
        raw_rows: $counts_raw.rows
        raw_assets: $counts_raw.assets
        daily_rows: $counts_daily.rows
        daily_assets: $counts_daily.assets
        selected_assets: $counts_selected.assets
        selected_daily_rows: $selected_daily_rows
        valid_rows: $counts_valid.rows
        bounds_removed_rows: ($selected_daily_rows - $counts_valid.rows)
        valid_assets: $counts_valid.assets
        weekly_rows: $counts_weekly.rows
        weekly_assets: $counts_weekly.assets
        unchanged_daily_share: ($unchanged_share | math round --precision 4)
        longest_unchanged_run: ($runs | get longest_run | math max)
        $"assets_with_run_over_($params.clean.max_unchanged_days)_days": (
            $runs | where longest_run > $params.clean.max_unchanged_days | length
        )
        weekly_jumps: $jumps.rows
        reversed_jumps: $jumps.reversed
        assets_ending_early: $assets_ending_early
        first_price_week: ($counts_daily.first_week | format date "%Y-%m-%d")
        last_price_day: ($counts_daily.last_day | format date "%Y-%m-%d")
        observed_share: (share-text $counts_cleaned.observed $total)
        composite_close_share: (share-text $counts_cleaned.composite_rows $total)
        buff_close_share: (share-text $counts_cleaned.buff_rows $total)
        steam_24h_share: (share-text $counts_cleaned.active_rows $total)
        zero_returns: $counts_cleaned.zero_returns
        capped_returns: $counts_cleaned.capped_returns
        missing_rarity_share: (share-text $counts_cleaned.missing_rarity $total)
        assets_below_one: $cheap_assets
        first_week: ($counts_cleaned.first_week | format date "%Y-%m-%d")
        last_observed_week: ($last_observed | format date "%Y-%m-%d")
    }
    | metrics-from
}
