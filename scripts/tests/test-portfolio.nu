use std/assert

use ../lib/helpers.nu [winsorize-return metric-record]

use ../lib/portfolio.nu [
    buy-and-hold
    eligible-assets
    portfolio-returns
    portfolio-summary
]

use ../lib/stats.nu [weekly-raw-return]

# The portfolio charges the sale fee only on the last week, and the return is capped.
let flat_values = [
    {week: (2021-01-04 | into datetime), value: 100.0}
    {week: (2021-01-11 | into datetime), value: 100.0}
]

let flat = (portfolio-returns $flat_values)

assert equal ($flat | get return | last) (-0.15)

let doubled_values = [
    {week: (2021-01-04 | into datetime), value: 100.0}
    {week: (2021-01-11 | into datetime), value: 300.0}
]

let doubled = (portfolio-returns $doubled_values)

assert equal ($doubled | get return | last) 1.0

let rising = (
    portfolio-returns [
        {week: (2021-01-04 | into datetime), value: 100.0}
        {week: (2021-01-11 | into datetime), value: 110.0}
        {week: (2021-01-18 | into datetime), value: 121.0}
    ]
)

let returns = ($rising | get return)

assert equal ($returns | first) null
assert equal (($returns | skip 1 | first) | math round --precision 6) 0.1

# The last week also pays the sale fee: 0.85 x 121 / 110 - 1.
assert equal (($returns | skip 2 | first) | math round --precision 6) (-0.065)

# The eligible assets respect the k count and raise on an excessive k.
let candidates = (
    [[name initial_price final_price mean_return return_stddev negative_std];
        [A 100.0 200.0 0.05 0.5 0.05]
        [B 100.0 150.0 0.03 0.1 0.05]
    ]
    | polars into-df
)

let selected = (eligible-assets $candidates --k 1 | polars select name | polars collect | polars into-nu)

assert equal ($selected | length) 1
assert equal ($selected | first | get name) "A"

# The ranking rule picks a different asset when it ranks by Sharpe.
let by_sharpe = (
    eligible-assets $candidates --k 1 --rank sharpe --roi 0 --sharpe 0 --sortino 0
    | polars select name
    | polars collect
    | polars into-nu
)

assert equal ($by_sharpe | first | get name) "B"

let failed = (
    try {
        eligible-assets $candidates --k 3 | polars collect

        false
    } catch {
        true
    }
)

assert $failed

# Build a weekly price frame with the period and the capped return. The first seven weeks are training.
def price-frame [series: list] {
    let weeks = (seq date --begin-date 2021-01-04 --end-date 2021-03-08 --increment 1wk)

    $series
    | each {|asset|
        $asset.prices | enumerate | each {|row|
            {
                name: $asset.name
                week: ($weeks | get --optional $row.index | into datetime)
                price: $row.item
                period: (if $row.index < 7 { "training" } else { "testing" })
            }
        }
    }
    | flatten
    | polars into-df
    | polars with-column (polars col week | polars cast date | polars as week)
    | polars sort-by name week
    | polars with-column (weekly-raw-return price | polars as raw_return)
    | polars with-column (winsorize-return (polars col raw_return) | polars as return)
    | polars collect
}

# The buy-and-hold selects the asset with the best training ROI and holds it.
let prices_a = [
    100.0 120.0 90.0 120.0 100.0
    120.0 140.0 120.0 100.0 120.0
]

let prices_b = [
    100.0 90.0 100.0 90.0 100.0
    90.0 80.0 90.0 100.0 90.0
]

let prices = (
    price-frame [
        {name: "A", prices: $prices_a}
        {name: "B", prices: $prices_b}
    ]
)

let rows = ($prices | buy-and-hold --k 1 --roi 0 --sharpe 0 --sortino 0)

assert equal ($rows | length) 3
assert equal ($rows | first | get return) null
assert equal (($rows | last | get return) | math round --precision 6) 0.02

# An asset that stops in the testing weeks keeps its last value, and the portfolio keeps every testing week.
let short_a = [
    100.0 120.0 90.0 120.0 100.0
    120.0 140.0 130.0 140.0
]

let dead = (
    price-frame [
        {name: "A", prices: $short_a}
        {name: "B", prices: $prices_b}
    ]
)

let dead_rows = ($dead | buy-and-hold --k 1 --roi 0 --sharpe 0 --sortino 0)

assert equal ($dead_rows | length) 3
assert equal (($dead_rows | last | get return) | math round --precision 6) (-0.15)

# The ratios use the standard deviation of the negative weeks. The summary repeats them on the weekly scale.
let ratio_values = [
    {week: (2021-01-04 | into datetime), value: 100.0}
    {week: (2021-01-11 | into datetime), value: 110.0}
    {week: (2021-01-18 | into datetime), value: 99.0}
    {week: (2021-01-25 | into datetime), value: 108.0}
    {week: (2021-02-01 | into datetime), value: 100.0}
]

let ratio_rows = (portfolio-returns $ratio_values)

assert equal (($ratio_rows | first | get sharpe) | math round --precision 4) (-0.1999)
assert equal (($ratio_rows | first | get sortino) | math round --precision 4) (-0.382)
assert equal (($ratio_rows | first | get roi) | math round --precision 4) (-0.15)

let summary = (portfolio-summary $ratio_rows --assets 1 | metric-record)

assert equal $summary.sale_fee "15"
assert equal $summary.roi "-15.00%"
assert equal $summary.sharpe "-0.20"
assert equal $summary.sortino "-0.38"
