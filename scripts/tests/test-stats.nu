use std/assert

use ../lib/stats.nu [
    autocorrelation
    safe-ratio
    sample-std
    moment-expressions
    shape-measures
    week-index
    weekly-raw-return
]

use ../lib/helpers.nu [winsorize-return]

# The first week has no return, the next is capped, and the last is negative.
let prices = (
    [[name week price]; [A 1 100.0] [A 2 200.0] [A 3 50.0] [A 4 300.0]]
    | polars into-df
    | polars with-column (weekly-raw-return price | polars as raw_return)
    | polars with-column (winsorize-return (polars col raw_return) | polars as return)
    | polars collect
    | polars into-nu
)

assert equal ($prices | get raw_return | first) null
assert equal ($prices | get return | skip 1 | first) 1.0
assert equal ($prices | get return | skip 2 | first) (-0.75)
assert equal ($prices | get raw_return | skip 3 | first) 5.0
assert equal ($prices | get return | skip 3 | first) 1.0

# The week index numbers the sorted unique weeks from one.
let weeks = ([[week]; [2021-01-11] [2021-01-04] [2021-01-18] [2021-01-04]] | polars into-df)
let index = ($weeks | week-index | polars into-nu)

assert equal ($index | get week_number) [1 2 3]

# The daily return restarts at null on each week.

# The ratio is null when the denominator is null, zero or not positive.
assert equal (safe-ratio 0.05 null) null
assert equal (safe-ratio 0.05 0.0) null
assert equal (safe-ratio 0.05 (-0.1)) null
assert equal (safe-ratio null 0.5) null
assert equal (safe-ratio 0.05 0.25) 0.2

# The sample deviation needs two values.
assert equal (sample-std []) null
assert equal (sample-std [0.1]) null
assert equal (sample-std [0.1 0.3] | math round --precision 6) 0.141421
