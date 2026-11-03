use std/assert

use ../lib/output.nu [msg]

# Check that the notebooks read the named flags that scripts/thesis.nu passes.
const ROOT = (path self | path dirname | path dirname | path dirname)

let work = (mktemp --directory)
let prices = ($work | path join "prices.parquet")
let market = ($work | path join "market.parquet")
let output = ($work | path join "images")
let days = (1..40 | each {|index| (2021-01-04 | into datetime) + ($index * 1wk) })

let frame = (
    $days
    | each {|week|
        {week: $week, market_return: 0.01, market_index: 1.0}
    }
)

$frame
| polars into-df
| polars with-column (polars col week | polars cast date | polars as week)
| polars save $market

let prices_frame = (
    $frame
    | each {|row|
        [
            {name: "A", week: $row.week, return: 0.02, raw_return: 0.02}
            {name: "B", week: $row.week, return: (-0.01), raw_return: (-0.01)}
        ]
    }
    | flatten
)

$prices_frame
| polars into-df
| polars with-column (polars col week | polars cast date | polars as week)
| polars save $prices

# The charts notebook writes one PDF for each chart.
let charts = (
    python ($ROOT | path join "scripts/nb/charts.py")
    --source $prices
    --market $market
    --output $output
    | complete
)

assert equal $charts.exit_code 0

for name in [coverage market returns_histogram] {
    let path = ($output | path join $"($name).pdf")

    assert ($path | path exists)
    assert (((ls $path | first | get size) | into int) > 0)
}

msg $"charts notebook wrote 3 PDF files in ($work)"

# The model notebook stops with code 1 when the dataset is missing.
let model = (
    python ($ROOT | path join "scripts/nb/model.py")
    --dataset ($work | path join "missing.parquet")
    --output ($work | path join "predictions.parquet")
    | complete
)

assert equal $model.exit_code 1
assert str contains $model.stderr "missing dataset"

msg "model notebook stops on a missing dataset"

# The command stops when a notebook fails, so a missing file is an error.
let failed = (nu ($ROOT | path join "scripts" "thesis.nu") charts ($work | path join "missing.parquet") | complete)

assert equal $failed.exit_code 1

msg "charts stops on a missing source file"

rm --recursive --force $work
