use std/assert

use ../lib/params.nu [load-params]

# params.nuon is a data file, so the parser does not check it. Check the shape and the ranges here.
let params = (load-params)

# The window is two dates in order.
let first = ($params.collection.first_date | into datetime)
let last = ($params.collection.last_date | into datetime)

assert ($first < $last)

# The factors and shares are floats in range.
assert ($params.clean.training_share > 0 and $params.clean.training_share < 1)
assert ($params.clean.min_price_multiple > 0)
assert ($params.clean.max_price_multiple > $params.clean.min_price_multiple)
assert ($params.portfolio.net_sale_share > 0 and $params.portfolio.net_sale_share < 1)

# The counts are positive ints.
for value in [
    $params.clean.min_observations
    $params.clean.max_stale_weeks
    $params.clean.max_unchanged_days
    $params.eda.item_min_weeks
] {
    assert (($value | describe) == "int")
    assert ($value > 0)
}

# The price and ratio thresholds are floats.
for value in [
    $params.return_cap
    $params.clean.min_mean_price
    $params.portfolio.min_roi
    $params.portfolio.min_sharpe
    $params.portfolio.min_sortino
] {
    assert (($value | describe) == "float")
}

assert ($params.return_cap > 0)

# Every sale period has a known season and starts before it ends.
let seasons = ["spring" "summer" "autumn" "winter"]

for period in $params.sale_periods {
    assert ($period.season in $seasons)
    assert (($period.start | into datetime) <= ($period.end | into datetime))
}
