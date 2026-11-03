use std/assert

use ../lib/helpers.nu [metric-record number-text]

use ../lib/eda.nu [
    activity-summary
    coverage-daily
    coverage-items
    launch-period-groups
    market-dynamics
    market-series
    quality-metrics
    return-distribution
    return-statistics
    source-comparison
]

# Build a frame from a table and cast its week column to a date.
def weekly-frame [rows: table, column: string = week] {
    $rows
    | polars into-df
    | polars with-column (polars col $column | polars cast date | polars as $column)
    | polars collect
}

# A small cleaned prices table with two assets and three rows.
let prices = (
    [[name week return observed]; [A 1 0.1 1] [A 2 (-0.1) 1] [B 1 0.2 1]]
    | polars into-df
    | polars collect
)

# The quality metrics match hand-computed values.
let quality = (quality-metrics $prices | metric-record | into record)

assert equal $quality.records "3"
assert equal $quality.assets "2"
assert equal $quality.weeks "2"
assert equal $quality.min_weeks_per_asset "1"
assert equal $quality.avg_weeks_per_asset "1.5"
assert equal $quality.max_weeks_per_asset "2"
assert equal $quality.positive_return_weeks "2"
assert equal $quality.negative_return_weeks "1"
assert equal $quality.zero_return_weeks "0"

# The top rows hold only the assets with enough weeks. The rest and overall rows pool every weekly return. The item Z has one week, so it falls into the rest row.
let pooled_prices = (
    [[name week return];
        [X 1 0.3] [X 2 0.1] [X 3 0.2]
        [Y 1 0.1] [Y 2 (-0.1)]
        [Z 1 0.9]
    ]
    | polars into-df
    | polars collect
)

let summary = (return-statistics $pooled_prices --min-weeks 2)

assert equal ($summary | get name) ["X" "Y" "rest" "overall"]
assert equal ($summary | first | get rank_n) 1
assert equal ($summary | where name == "rest" | first | get rank_n) null
assert equal ($summary | where name == "rest" | first | get mean_return) 0.9
assert equal (($summary | last | get mean_return) | math round --precision 6) 0.25
assert equal ($summary | last | get n_weeks) 2.0

# The coverage counts the asset-weeks with a real price and reads the audit dates.
let coverage_prices = (
    weekly-frame [[name week observed]; ["A" 2021-01-04 1] ["A" 2021-01-11 0] ["B" 2021-01-04 1]]
)

let coverage = (
    coverage-daily $coverage_prices {first_price_week: "2020-12-28", last_price_day: "2021-01-12"}
    | metric-record
    | into record
)

assert equal $coverage.first_price_week "28/12/2020"
assert equal $coverage.first_return_week "04/01/2021"
assert equal $coverage.last_price_day "12/01/2021"
assert equal $coverage.return_weeks "2"
assert equal $coverage.asset_week_share "66.67%"
assert equal $coverage.max_assets_per_week "2"

# The persistence table counts the raw assets and the selected assets for each range.
let assets = (
    [[name positive_weeks reason]; [A 10 selected] [B 10 low_price] [C 130 selected]]
    | polars into-df
)

let persistence = (coverage-items $assets)

assert equal ($persistence | length) 6
assert equal ($persistence | first) {weeks_range: "< 25", universe_assets: 2, selected_assets: 1}
assert equal ($persistence | last) {weeks_range: "125+", universe_assets: 1, selected_assets: 1}

# The launch period table groups the assets by launch half-year and rejection reason.
let launches = (
    weekly-frame [[name first_week reason];
        [A 2021-01-04 selected]
        [B 2021-08-02 low_price]
        [C 2021-01-11 no_training_data]
    ] first_week
)

let groups = (launch-period-groups $launches)

assert equal ($groups | get launch_period) ["2021-H1" "2021-H2"]
assert equal ($groups | first | get assets) 2
assert equal ($groups | first | get selected) 1
assert equal ($groups | first | get no_training_data) 1
assert equal ($groups | last | get low_price) 1

# The distribution compares the capped and the raw return.
let distribution_prices = (
    [[name return raw_return]; [A 0.1 0.1] [A (-0.1) (-0.1)] [B 1.0 3.0] [B 0.0 0.0]]
    | polars into-df
    | polars collect
)

let distribution = (return-distribution $distribution_prices)

assert equal ($distribution | get label) ["capped" "raw"]
assert equal ($distribution | get mean) [0.25 0.75]
assert equal ($distribution | get share_above_half) [0.25 0.25]
assert equal ($distribution | first | get n) 4

# The market return is the equal-weight mean of the weekly returns, and the index compounds it.
let market_prices = (
    weekly-frame [[name week return];
        [A 2021-01-04 0.1]
        [B 2021-01-04 0.3]
        [A 2021-01-11 (-0.5)]
        [B 2021-01-11 (-0.1)]
    ]
)

let market = (market-series $market_prices)

assert equal ($market | get market_return | each {|value| $value | math round --precision 6 }) [0.2 (-0.3)]
assert equal ($market | get market_index | each {|value| $value | math round --precision 6 }) [1.2 0.84]
assert equal ($market | get assets) [2 2]

# Two assets that equal the market have a market correlation of one.
let mirror = (
    weekly-frame [[name week return];
        [A 2021-01-04 0.1] [A 2021-01-11 (-0.1)] [A 2021-01-18 0.2] [A 2021-01-25 0.0] [A 2021-02-01 0.3] [A 2021-02-08 (-0.2)]
        [B 2021-01-04 0.1] [B 2021-01-11 (-0.1)] [B 2021-01-18 0.2] [B 2021-01-25 0.0] [B 2021-02-01 0.3] [B 2021-02-08 (-0.2)]
    ]
)

let dynamics = (
    market-dynamics $mirror (market-series $mirror) --min-weeks 2
    | metric-record
    | into record
)

assert equal ($dynamics.mean_market_correlation | into float | math round --precision 4) 1.0
assert equal ($dynamics.median_market_correlation | into float | math round --precision 4) 1.0

# A composite that doubles the Steam price has a price ratio of 0.5 and a return correlation of one. The BUFF price is half the Steam price.
let source_prices = (
    weekly-frame [[name week price return observed composite_close buff_close];
        [A 2021-01-04 10.0 0.0 1 20.0 5.0]
        [A 2021-01-11 12.0 0.2 1 24.0 6.0]
        [A 2021-01-18 9.0 (-0.25) 1 18.0 4.5]
        [A 2021-01-25 18.0 1.0 1 36.0 9.0]
    ]
)

let sources = (source-comparison $source_prices)
let composite = ($sources | where source == "composite" | first)

assert equal $composite.week_share 1.0
assert equal $composite.median_ratio 0.5
assert equal $composite.pairs 3
assert equal ($composite.return_correlation | math round --precision 4) 1.0
assert equal ($sources | where source == "buff" | first | get median_ratio) 2.0

# No item reaches US$ 800, so the expensive row has no ratio.
assert equal ($sources | where source == "composite_800" | first | get median_ratio) null

# The activity summary counts the item-weeks by bucket.
let activity_prices = (
    weekly-frame [[name week observed active_days]; [A 2021-01-04 1 0] [A 2021-01-11 1 2] [B 2021-01-04 1 7]]
)

let activity = (activity-summary $activity_prices)

assert equal ($activity | get item_weeks) [1 1 0 0 1]

# Sortino uses the standard deviation of the negative weeks. Values 0.03 0.05 -0.02 0.04 -0.01 give a mean of 0.018, a negative standard deviation of 0.007071 and a ratio of 2.5456. The table has no annualized column.
let ratio_prices = (
    weekly-frame [[name week return]; [A 2021-01-04 0.03] [A 2021-01-11 0.05] [A 2021-01-18 (-0.02)] [A 2021-01-25 0.04] [A 2021-02-01 (-0.01)]]
)

let ratio_rows = (return-statistics $ratio_prices --min-weeks 1)
let ratios = ($ratio_rows | where name == "overall" | first)

assert equal (($ratios.negative_returns_std) | math round --precision 6) 0.007071
assert equal (($ratios.sortino) | math round --precision 4) 2.5456

let expected = [
    name rank_n mean_return median_return min_return max_return std_return
    negative_returns_std n_weeks sharpe sortino
]

assert equal ($ratio_rows | columns) $expected

# Sortino is null with a single negative week.
let one_negative = (
    weekly-frame [[name week return]; [A 2021-01-04 0.03] [A 2021-01-11 (-0.02)]]
)

let single = (return-statistics $one_negative --min-weeks 1 | where name == "overall" | first)

assert equal $single.sortino null

# The quality counts zero returns.
let zero_prices = ([[name week return observed]; [A 1 0.0 1]] | polars into-df | polars collect)

let zero_quality = (
    quality-metrics $zero_prices
    | metric-record
    | into record
)

assert equal $zero_quality.zero_return_weeks "1"

# The launch period groups count each reason.
let launch_assets = (
    [[name first_week reason];
        [A 2021-02-01 "selected"]
        [B 2021-03-01 "low_price"]
        [C 2021-09-01 "selected"]
    ]
    | polars into-df
    | polars with-column (polars col first_week | polars cast date | polars as first_week)
    | polars collect
)

let groups = (launch-period-groups $launch_assets)

assert equal ($groups | get launch_period) ["2021-H1" "2021-H2"]
assert equal ($groups | get selected) [1 1]
assert equal ($groups | get low_price) [1 0]
assert equal ($groups | get assets) [2 1]

# The number text keeps four decimals.
assert equal (0.04 | number-text) "0.0400"
assert equal (-0.1717123 | number-text) "-0.1717"
