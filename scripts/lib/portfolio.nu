use ./helpers.nu [winsorize-number fail mean-or-null metrics-from number-text]
use ./output.nu [msg]
use ./params.nu [load-params]
use ./stats.nu [safe-ratio sample-std sharpe sortino]

# Rank the eligible assets by one training column and keep the requested count.
export def eligible-assets [
    candidates
    --k: int
    --rank: string = "roi"
    --roi: float
    --sharpe: float
    --sortino: float
] {
    let params = (load-params)
    let roi_threshold = $roi | default $params.portfolio.min_roi | into float
    let sharpe_threshold = $sharpe | default $params.portfolio.min_sharpe | into float
    let sortino_threshold = $sortino | default $params.portfolio.min_sortino | into float
    let has_spread = (((polars col return_stddev) > 0) and ((polars col negative_std) > 0))
    let meets_roi = ((polars col roi) >= $roi_threshold)
    let meets_sharpe = ((polars col sharpe) >= $sharpe_threshold)
    let meets_sortino = ((polars col sortino) >= $sortino_threshold)

    if $k == null {
        fail "--k is required" $k --label "portfolio size"
    }

    let ranked = (
        $candidates
        | polars filter $has_spread
        | polars with-column (
            ((polars col final_price) * $params.portfolio.net_sale_share / (polars col initial_price) - 1) | polars as roi
        )
        | polars with-column ((sharpe mean_return return_stddev) | polars as sharpe)
        | polars with-column ((sortino mean_return negative_std) | polars as sortino)
        | polars filter ($meets_roi and $meets_sharpe and $meets_sortino)
        | polars sort-by $rank --reverse [true]
        | polars collect
    )

    let count = $ranked | polars into-nu | length

    msg --level debug $"eligible: ($count) assets, requested ($k)"

    if $count < $k {
        fail $"requested K value ($k) exceeds eligible asset count ($count)" $k --label "portfolio size"
    }

    $ranked | polars slice 0 $k
}

# Turn weekly portfolio values into returns and portfolio-level metrics.
export def portfolio-returns [values: list<any>]: nothing -> table {
    let count = $values | length
    let net_sale_share = (load-params).portfolio.net_sale_share

    if $count == 0 {
        fail "portfolio has no testing weeks" $values --label "portfolio values"
    }

    let frame = (
        $values
        | polars into-df
        | polars sort-by week
        | polars with-column (polars col value | polars shift 1 | polars as previous)
        | polars collect
        | polars into-nu
    )

    let rows = (
        $frame | enumerate | each {|row|
            let value = $row.item.value
            let previous = $row.item.previous

            let week_return = (
                if $previous == null {
                    null
                } else {
                    let gross = (
                        if $row.index == $count - 1 {
                            $net_sale_share * $value / $previous - 1
                        } else {
                            $value / $previous - 1
                        }
                    )
                    winsorize-number $gross
                }
            )
            {week: $row.item.week, value: $value, return: $week_return}
        }
    )

    let returns = $rows | get return | compact
    let average = $returns | mean-or-null
    let deviation = (sample-std $returns)
    let negatives = $returns | where $it < 0
    let negative_std = (sample-std $negatives)
    let initial = $frame | first | get value
    let final = $frame | last | get value
    let roi = ($net_sale_share * $final / $initial - 1)

    msg --level debug $"portfolio: ($count) weeks, roi ($roi)"

    let sharpe = (safe-ratio $average $deviation)
    let sortino = (safe-ratio $average $negative_std)
    $rows | each {|row|
        $row | insert roi $roi | insert sharpe $sharpe | insert sortino $sortino
    }
}

# Format one nullable ratio with two decimals, or "n/d" when the ratio is null.
def ratio-text []: any -> string {
    let value = $in

    if $value == null { return "n/d" }

    $value | number-text 2
}

# Summarize the portfolio ratios. They are weekly.
export def portfolio-summary [rows: table, --assets: int]: nothing -> table {
    let first = $rows | first
    let net_sale_share = (load-params).portfolio.net_sale_share

    {
        assets: $assets
        weeks: ($rows | length)
        sale_fee: ((1 - $net_sale_share) * 100 | math round)
        roi: $"($first.roi * 100 | number-text 2)%"
        sharpe: ($first.sharpe | ratio-text)
        sortino: ($first.sortino | ratio-text)
    }
    | metrics-from
}

# Return the names that have a price in the first testing week.
def buyable-names [series]: nothing -> any {
    let is_testing = ((polars col period) == "testing")
    let first_test_week = (
        $series
        | polars filter $is_testing
        | polars select (polars col week | polars min | polars as week)
        | polars collect
    )

    $series | polars join $first_test_week week week --inner | polars select name
}

# Hold the selected names with equal initial weights and return the weekly rows.
def hold [spec: record]: nothing -> table {
    let series = $spec.series
    let names = $spec.names
    let count = $spec.count
    let is_testing = ((polars col period) == "testing")
    let is_past_last = ((polars col last_week) < (polars col week))

    let positions = (
        $series
        | polars filter $is_testing
        | polars join $names name name --inner
        | polars sort-by name week
        | polars with-column (
            (polars col price | polars first | polars over (polars col name)) | polars as initial_price
        )
        | polars with-column (((polars col price) / (polars col initial_price) / $count) | polars as weight)
    )

    let test_weeks = (
        $series
        | polars filter $is_testing
        | polars select week
        | polars unique
    )

    let carried = (
        $positions
        | polars group-by name
        | polars agg [
            (polars col week | polars max | polars as last_week)
            (polars col weight | polars last | polars as last_weight)
        ]
        | polars join $test_weeks --cross
        | polars filter $is_past_last
        | polars group-by week
        | polars agg [(polars col last_weight | polars sum | polars as carried_weight)]
    )

    let values = (
        $test_weeks
        | polars join (
            $positions
            | polars group-by week
            | polars agg [(polars col weight | polars sum | polars as held_weight)]
        ) week week --left
        | polars join $carried week week --left
        | polars with-column (
            ((polars col held_weight | polars fill-null 0.0) + (polars col carried_weight | polars fill-null 0.0)) | polars as value
        )
        | polars select week value
        | polars sort-by week
        | polars collect
        | polars into-nu
    )
    portfolio-returns $values
}

# Build an equal-weight buy-and-hold portfolio for one portfolio size.
export def buy-and-hold [
    --k: int
    --rank: string = "roi"
    --roi: float
    --sharpe: float
    --sortino: float
]: any -> table {
    let prices = $in
    let params = (load-params)
    let roi_threshold = $roi | default $params.portfolio.min_roi | into float
    let sharpe_threshold = $sharpe | default $params.portfolio.min_sharpe | into float
    let sortino_threshold = $sortino | default $params.portfolio.min_sortino | into float
    let is_training = ((polars col period) == "training")
    let is_negative = ((polars col return) < 0)
    let is_training_negative = ($is_training and $is_negative)

    if $k == null {
        fail "--k is required" $k --label "portfolio size"
    }

    msg --level debug $"buy-and-hold: k=($k), rank=($rank)"

    if $k < 1 {
        fail "k must be positive" $k --label "portfolio size"
    }

    let series = $prices | polars sort-by name week
    let buyable = (buyable-names $series)

    let candidates = (
        $series
        | polars join $buyable name name --inner
        | polars filter $is_training
        | polars group-by name
        | polars agg [
            (polars col price | polars first | polars as initial_price)
            (polars col price | polars last | polars as final_price)
            (polars col return | polars mean | polars as mean_return)
            (polars col return | polars std | polars as return_stddev)
        ]
    )

    let negative_std = (
        $series
        | polars join $buyable name name --inner
        | polars filter $is_training_negative
        | polars group-by name
        | polars agg [(polars col return | polars std | polars as negative_std)]
    )

    let candidates = $candidates | polars join $negative_std name name --left | polars collect

    let selected = (
        eligible-assets $candidates --k $k --rank $rank --roi $roi_threshold --sharpe $sharpe_threshold --sortino $sortino_threshold
        | polars select name
    )

    hold {series: $series, names: $selected, count: $k}
}
