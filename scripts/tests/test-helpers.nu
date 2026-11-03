use std/assert

use ../lib/helpers.nu [fail mean-or-null metric-row number-text one-row round-text sale-season]

use ../lib/stats.nu [count-where]

# One row keeps the values of the first row of an aggregate.
let row = (
    [[name value]; [A 2.0] [B 4.0]]
    | polars into-df
    | polars select [
        (polars col value | polars mean | polars as mean_value)
        (polars len | polars as rows)
    ]
    | one-row
)

assert equal $row {mean_value: 3.0, rows: 2}

# The metric row converts every value to a string.
assert equal (metric-row "count" 3) {metric_name: count, metric_value: "3"}
assert equal (metric-row "share" 0.25) {metric_name: share, metric_value: "0.25"}
assert equal (metric-row "label" "ready") {metric_name: label, metric_value: "ready"}

# The number text pads the decimals and the round text does not.
assert equal (0.5 | number-text 2) "0.50"
assert equal (0.5 | round-text 2) "0.5"
assert equal (1.2345 | number-text) "1.2345"
assert equal (1.2345 | round-text 3) "1.235"

# The count counts the rows that meet the condition and returns zero for none.
let counts = (
    [[value]; [1.0] [-2.0] [0.0] [3.0]]
    | polars into-df
    | polars select [
        (count-where ((polars col value) > 0.0) | polars as positive)
        (count-where ((polars col value) < 0.0) | polars as negative)
        (count-where ((polars col value) > 10.0) | polars as large)
    ]
    | one-row
)

assert equal $counts {positive: 2, negative: 1, large: 0}

# `fail` reports the message, the label, and the line of the caller.
const ROOT = (path self | path dirname | path dirname | path dirname)

let dir = (mktemp --directory)
let script = ($dir | path join "failing.nu")

[
    $"use ($ROOT | path join 'scripts/lib/helpers.nu') [fail]"
    'let culprit = "files/raw"'
    'fail "boom" $culprit --label "raw directory"'
] | str join "\n" | save $script

let result = (nu $script | complete)

assert equal $result.exit_code 1
assert ($result.stderr =~ "boom")
assert ($result.stderr =~ "raw directory")
assert ($result.stderr =~ 'failing.nu:3')

rm --recursive --force $dir

# The mean ignores null values and is null when none remain.
assert equal ([0.1 null 0.3] | mean-or-null | math round --precision 6) 0.2
assert equal ([null null] | mean-or-null) null

# A week outside every sale period has no season.
assert equal (sale-season (2021-03-01 | into datetime)) "none"
