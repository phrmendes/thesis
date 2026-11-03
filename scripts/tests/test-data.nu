use std/assert

use ../lib/audit.nu [cleaning-audit]

use ../lib/clean.nu [asset-universe clean-stages cleaned-prices]

use ../lib/helpers.nu [metric-record]

# Build a raw frame from a table with the raw price columns.
def raw-frame [rows: table] {
    $rows
    | polars into-df
    | polars with-column (polars col date | polars cast date | polars as date)
    | polars collect
}

# Return one raw row without a Steam 24-hour, composite, or BUFF price.
def quote [row: record] {
    $row | merge {steam_24h: 0.0, composite_price: 0.0, buff_price: 0.0}
}

# The cleaned prices keep the last daily price of each week, repeat the last close into an empty week, drop the first week of each asset, and cap returns.
let raw = (
    raw-frame [[date name price steam_24h composite_price buff_price];
        [2021-01-04 "A" 10.0 9.0 11.0 0.0]
        [2021-01-06 "A" 12.0 0.0 13.0 0.0]
        [2021-01-12 "A" 20.0 19.0 21.0 0.0]
        [2021-01-18 "A" 5.0 0.0 6.0 0.0]
        [2021-01-25 "A" 20.0 0.0 21.0 0.0]
        [2021-02-01 "A" 10.0 0.0 11.0 0.0]
        [2021-02-08 "B" 100.0 0.0 101.0 0.0]
    ]
)

let items = ([[name rarity]; [A rare] [B common]] | polars into-df)
let stages = (clean-stages $raw --min-observations 1)
let cleaned = (cleaned-prices $stages --items $items | polars collect)
let is_a = ((polars col name) == "A")
let result = ($cleaned | polars filter $is_a | polars sort-by week | polars collect | polars into-nu)

assert equal ($result | length) 5

let returns = ($result | get return | each {|value| $value | math round --precision 6 })

assert equal $returns [0.666667 (-0.75) 1.0 (-0.5) 0.0]
assert equal ($result | get raw_return | skip 2 | first) 3.0
assert equal ($result | first | get price) 20.0
assert equal ($result | last | get price) 10.0
assert equal ($result | last | get observed) 0
assert equal ($result | last | get sale_season) "none"
assert equal ($result | first | get period) "training"
assert equal ($result | last | get period) "testing"

# Only the second row has a day with a Steam 24-hour price. The filled last week has none.
assert equal ($result | get active_days) [1 0 0 0 null]
assert equal ($result | get composite_close) [21.0 6.0 21.0 11.0 null]
assert equal ($result | get buff_close) [null null null null null]
assert equal ($result | first | get --optional roi) null

# The asset B has no training price, so the filter drops it.
assert equal ($cleaned | polars into-nu | where name == "B" | length) 0

# The shares count the weeks with a composite close, a Steam 24-hour price, or a BUFF close.
let audit_table = (cleaning-audit $stages $cleaned)
let metrics = ($audit_table | metric-record)

assert equal ($audit_table | length) 29

assert equal $metrics.composite_close_share "0.8"
assert equal $metrics.steam_24h_share "0.2"
assert equal $metrics.buff_close_share "0"

# The filter and the price reference use the training weeks only. Asset D costs 10 in the training weeks and 1000 later. The price bounds drop the later prices, and the fill stops after the stale limit.
let weeks = (seq date --begin-date 2021-01-04 --end-date 2021-03-08 --increment 1wk)

let late_rows = (
    $weeks | enumerate | each {|row|
        let day = ($row.item | into datetime)
        let price_d = (if $row.index < 4 { 10.0 } else { 1000.0 })

        [
            (quote {date: $day, name: "D", price: $price_d})
            (quote {date: $day, name: "P", price: 10.0})
        ]
        | append (if $row.index >= 7 { [(quote {date: $day, name: "L", price: 10.0})] } else { [] })
    } | flatten
)

let late_stages = (clean-stages (raw-frame $late_rows) --min-observations 1)
let late = (cleaned-prices $late_stages | polars collect | polars into-nu)
let rows_d = ($late | where name == "D" | sort-by week)

assert equal ($rows_d | length) 7
assert equal ($rows_d | get observed) [1 1 1 0 0 0 0]
assert equal ($rows_d | get price | math max) 10.0
assert equal ($late | where name == "L" | length) 0

# The asset table keeps the rejected assets with a reason.
let universe = (
    asset-universe $late_stages
    | polars collect
    | polars into-nu
)

assert equal ($universe | where name == "L" | first | get reason) "no_training_data"
assert equal ($universe | where name == "P" | first | get reason) "selected"
assert equal ($universe | where name == "P" | first | get positive_weeks) 10

# The weekly risk uses the daily prices inside each week.
let risky = (
    raw-frame [[date name price steam_24h composite_price buff_price];
        [2021-01-04 "R" 10.0 0.0 0.0 0.0]
        [2021-01-11 "R" 10.0 0.0 0.0 0.0]
        [2021-01-13 "R" 11.0 0.0 0.0 0.0]
        [2021-01-15 "R" 9.9 0.0 0.0 0.0]
        [2021-01-18 "R" 20.0 0.0 0.0 0.0]
    ]
)

let risky_items = ([[name rarity]; [R rare]] | polars into-df)
let risky_stages = (clean-stages $risky --min-observations 1)
let risky_cleaned = (cleaned-prices $risky_stages --items $risky_items | polars collect)
let risky_rows = ($risky_cleaned | polars into-nu)
let middle = ($risky_rows | first)
let final = ($risky_rows | last)

assert equal ($middle | get observed) 1
assert equal (($middle | get return) | math round --precision 6) (-0.01)
assert equal (($final | get raw_return) | math round --precision 6) 1.020202
assert equal ($final | get return) 1.0
assert equal ($final | get --optional intraweek_sharpe) null

# The audit counts the rows, the staleness, and the jumps.
let audit = (cleaning-audit $risky_stages $risky_cleaned | metric-record)

assert equal $audit.daily_rows "5"
assert equal $audit.selected_assets "1"
assert equal $audit.selected_daily_rows "5"
assert equal $audit.bounds_removed_rows "0"
assert equal $audit.weekly_rows "2"
assert equal $audit.unchanged_daily_share "0.25"
assert equal $audit.longest_unchanged_run "2"
assert equal $audit.weekly_jumps "1"
assert equal $audit.reversed_jumps "0"
assert equal $audit.assets_ending_early "0"
assert equal $audit.first_price_week "2021-01-04"
assert equal $audit.last_price_day "2021-01-18"
