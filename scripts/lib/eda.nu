use ./helpers.nu [
    winsorize-return
    fail
    metrics-from
    number-text
    one-row
    round-text
]
use ./params.nu [load-params]
use ./stats.nu [
    autocorrelation
    count-where
    moment-expressions
    safe-ratio
    shape-measures
    sharpe
    sortino
]

# Summarize temporal coverage and assets per week. The audit record gives the first price week and the last price day.
export def coverage-daily [prices, audit: record]: nothing -> table {
    let is_observed = ((polars col observed) == 1)
    let weekly = (
        $prices
        | polars filter $is_observed
        | polars group-by week
        | polars agg [(polars col name | polars count | polars as assets)]
        | polars sort-by week
        | polars collect
        | polars into-nu
    )

    if ($weekly | is-empty) {
        fail "cleaned prices are empty" $prices --label "prices"
    }

    let totals = (
        $prices
        | polars select [
            (polars len | polars as records)
            (polars col observed | polars sum | polars as observed)
            (polars col week | polars min | polars as first_week)
            (polars col week | polars n-unique | polars as weeks)
        ]
        | one-row
    )

    let observed_share = $totals.observed * 100.0 / $totals.records | round-text 2
    let assets = $weekly | get assets
    let first_price = $audit.first_price_week | into datetime | format date "%d/%m/%Y"
    let last_price = $audit.last_price_day | into datetime | format date "%d/%m/%Y"

    {
        first_price_week: $first_price
        first_return_week: ($totals.first_week | format date "%d/%m/%Y")
        last_price_day: $last_price
        return_weeks: ($totals.weeks | into string)
        asset_week_share: $"($observed_share)%"
        min_assets_per_week: ($assets | math min | into string)
        avg_assets_per_week: (
            $assets
            | math avg
            | math round
            | into int
            | into string
        )
        max_assets_per_week: ($assets | math max | into string)
    }
    | metrics-from
}

# Build one bucket expression: a when per bucket and otherwise the last label.
def bucket-expression [
    column: string
    output: string
    --buckets: list<any>
    --compare: closure
]: nothing -> any {
    $buckets
    | reduce --fold null {|bucket, chain|
        if ($bucket.upper == null) { return $chain }

        let upper = $bucket.upper | into float
        let condition = (do $compare $column $upper)

        if ($chain | describe) == "nothing" {
            polars when $condition $bucket.label
        } else {
            $chain | polars when $condition $bucket.label
        }
    }
    | polars otherwise ($buckets | last | get label)
    | polars as $output
}

# Group the raw assets by their number of weeks with a positive price. The universe column counts every asset. The selected column counts the assets that pass the filter.
export def coverage-items [assets]: nothing -> table {
    let buckets = [
        {label: "< 25", upper: 25}
        {label: "25-49", upper: 50}
        {label: "50-74", upper: 75}
        {label: "75-99", upper: 100}
        {label: "100-124", upper: 125}
        {label: "125+", upper: null}
    ]

    let weeks_range = (
        bucket-expression positive_weeks weeks_range --buckets $buckets --compare {|column, upper|
            (polars col $column) < $upper
        }
    )

    let selected = (
        polars when ((polars col reason) == "selected") 1
        | polars otherwise 0
        | polars as is_selected
    )

    let counts = (
        $assets
        | polars with-column $weeks_range
        | polars with-column $selected
        | polars group-by weeks_range
        | polars agg [
            (polars col name | polars count | polars as universe_assets)
            (polars col is_selected | polars sum | polars as selected_assets)
        ]
        | polars collect
        | polars into-nu
    )

    $buckets
    | get label
    | each {|range|
        let found = $counts | where weeks_range == $range

        if ($found | is-empty) {
            {weeks_range: $range, universe_assets: 0, selected_assets: 0}
        } else {
            $found | first | select weeks_range universe_assets selected_assets
        }
    }
}

# Return the launch half-year label of one asset: the year and H1 or H2.
def launch-period-label [first_week: datetime]: nothing -> string {
    let month = $first_week | format date "%m" | into int
    let half = (if $month <= 6 { 1 } else { 2 })
    let year = $first_week | format date "%Y"

    $"($year)-H($half)"
}

# Count the raw assets by launch half-year, with the selection result.
export def launch-period-groups [assets]: nothing -> table {
    $assets
    | polars collect
    | polars into-nu
    | each {|row|
        {launch_period: (launch-period-label $row.first_week), reason: $row.reason}
    }
    | group-by launch_period
    | items {|period, rows|
        let by_reason = (
            $rows | group-by reason | items {|reason, found| {$reason: ($found | length)} } | into record
        )

        {
            launch_period: $period
            assets: ($by_reason | values | math sum)
            selected: ($by_reason.selected? | default 0)
            low_price: ($by_reason.low_price? | default 0)
            few_observations: ($by_reason.few_observations? | default 0)
            no_training_data: ($by_reason.no_training_data? | default 0)
        }
    }
    | sort-by launch_period
}

# Summarize size, return signs, coverage, and metric availability.
export def quality-metrics [prices]: nothing -> table {
    let per_asset = (
        $prices
        | polars group-by name
        | polars agg [(polars col observed | polars sum | polars as n)]
    )

    let totals = (
        $prices
        | polars select [
            (polars len | polars as records)
            (polars col name | polars n-unique | polars as assets)
            (polars col week | polars n-unique | polars as weeks)
            (polars col observed | polars sum | polars as observed)
        ]
        | one-row
    )

    let week_stats = (
        $per_asset
        | polars select [
            (polars col n | polars min | polars as min_weeks)
            (polars col n | polars mean | polars as avg_weeks)
            (polars col n | polars max | polars as max_weeks)
        ]
        | one-row
    )

    let signs = (
        $prices
        | polars select [
            (count-where ((polars col return) > 0) | polars as positive_weeks)
            (count-where ((polars col return) < 0) | polars as negative_weeks)
            (count-where ((polars col return) == 0.0) | polars as zero_return_weeks)
        ]
        | one-row
    )

    {
        records: $totals.records
        assets: $totals.assets
        weeks: $totals.weeks
        min_weeks_per_asset: $week_stats.min_weeks
        avg_weeks_per_asset: ($week_stats.avg_weeks | math round --precision 1)
        max_weeks_per_asset: $week_stats.max_weeks
        positive_return_weeks: $signs.positive_weeks
        negative_return_weeks: $signs.negative_weeks
        zero_return_weeks: $signs.zero_return_weeks
        filled_rows: ($totals.records - $totals.observed)
    }
    | metrics-from
}

# Aggregate the pooled statistics of every weekly return in one frame.
def pooled-row [frame, label: string]: nothing -> record {
    let is_negative = ((polars col return) < 0)

    let statistics = (
        $frame
        | polars select [
            (polars col return | polars mean | polars as mean_return)
            (polars col return | polars median | polars as median_return)
            (polars col return | polars min | polars as min_return)
            (polars col return | polars max | polars as max_return)
            (polars col return | polars std | polars as std_return)
            ((polars len) / (polars col name | polars n-unique) | polars as n_weeks)
        ]
        | one-row
    )

    let negative_std = (
        $frame
        | polars filter $is_negative
        | polars select (polars col return | polars std | polars as negative_returns_std)
        | one-row
        | get negative_returns_std
    )

    let sharpe_ratio = (safe-ratio $statistics.mean_return $statistics.std_return)
    let sortino_ratio = (safe-ratio $statistics.mean_return $negative_std)

    {
        name: $label
        rank_n: null
        mean_return: $statistics.mean_return
        median_return: $statistics.median_return
        min_return: $statistics.min_return
        max_return: $statistics.max_return
        std_return: $statistics.std_return
        negative_returns_std: $negative_std
        n_weeks: $statistics.n_weeks
        sharpe: $sharpe_ratio
        sortino: $sortino_ratio
    }
}

# Number the rows from one in descending mean return order.
def rank-by-mean-return []: table -> table {
    sort-by mean_return --reverse
    | enumerate
    | each {|row| $row.item | insert rank_n ($row.index + 1) }
}

# Summarize weekly returns. The top rows are the best items with enough weeks. The rest and overall rows pool every weekly return of their items.
export def return-statistics [prices, --min-weeks: int]: nothing -> table {
    let min_weeks = $min_weeks | default (load-params).eda.item_min_weeks | into int
    let is_negative = ((polars col return) < 0)
    let has_spread = ((polars col std_return) > 0)
    let has_negative_spread = ((polars col negative_returns_std) > 0)
    let has_enough_weeks = ((polars col n_weeks) >= $min_weeks)

    let asset_stats = (
        $prices
        | polars group-by name
        | polars agg [
            (polars col return | polars mean | polars as mean_return)
            (polars col return | polars median | polars as median_return)
            (polars col return | polars min | polars as min_return)
            (polars col return | polars max | polars as max_return)
            (polars col return | polars std | polars as std_return)
            (polars col return | polars count | polars as n_weeks)
        ]
    )

    let negative_std = (
        $prices
        | polars filter $is_negative
        | polars group-by name
        | polars agg [(polars col return | polars std | polars as negative_returns_std)]
    )

    let sharpe_rows = (
        $asset_stats
        | polars filter $has_spread
        | polars with-column ((sharpe mean_return std_return) | polars as sharpe)
        | polars select name sharpe
    )

    let sortino_rows = (
        $asset_stats
        | polars join $negative_std name name --inner
        | polars filter $has_negative_spread
        | polars with-column ((sortino mean_return negative_returns_std) | polars as sortino)
        | polars select name sortino
    )

    let metric_columns = [
        mean_return
        median_return
        min_return
        max_return
        std_return
        negative_returns_std
        n_weeks
        sharpe
        sortino
    ]

    let ranked_frame = (
        $asset_stats
        | polars filter $has_enough_weeks
        | polars join $negative_std name name --left
        | polars join $sharpe_rows name name --left
        | polars join $sortino_rows name name --left
        | polars collect
    )

    let ranked = (
        $ranked_frame
        | polars into-nu
        | each {|row| $row | merge {n_weeks: ($row.n_weeks | into float)} }
        | rank-by-mean-return
    )

    let top = $ranked | first 10 | select name rank_n ...$metric_columns

    let top_names = (
        if ($top | is-empty) {
            [[name top]; ["" 1]]
        } else {
            $top | select name | insert top 1
        }
        | polars into-df
    )

    let is_not_top = polars col top | polars is-null
    let rest = (
        $prices
        | polars join $top_names name name --left
        | polars filter $is_not_top
    )

    $top | append [
        (pooled-row $rest rest)
        (pooled-row $prices overall)
    ]
}

# Summarize the pooled distribution of one return column.
def distribution-row [prices, spec: record]: nothing -> record {
    let column = $spec.column
    let column_value = (polars col $column)
    let above_half = (
        polars when ((($column_value | polars math abs)) > 0.5) 1.0
        | polars otherwise 0.0
        | polars mean
        | polars as share_above_half
    )

    let statistics = (
        $prices
        | polars select (
            [
                (polars len | polars as n)
                ($column_value | polars std | polars as std)
                ($column_value | polars quantile 0.01 | polars as p01)
                ($column_value | polars quantile 0.05 | polars as p05)
                ($column_value | polars quantile 0.5 | polars as p50)
                ($column_value | polars quantile 0.95 | polars as p95)
                ($column_value | polars quantile 0.99 | polars as p99)
                $above_half
            ]
            | append (moment-expressions $column)
        )
        | one-row
    )

    let shape = (shape-measures $statistics)

    {
        label: $spec.label
        n: $statistics.n
        mean: $statistics.m1
        std: $statistics.std
        skewness: $shape.skewness
        excess_kurtosis: $shape.excess_kurtosis
        p01: $statistics.p01
        p05: $statistics.p05
        p50: $statistics.p50
        p95: $statistics.p95
        p99: $statistics.p99
        share_above_half: $statistics.share_above_half
    }
}

# Compare the capped weekly return with the raw weekly return.
export def return-distribution [prices]: nothing -> table {
    [
        (distribution-row $prices {column: return, label: capped})
        (distribution-row $prices {column: raw_return, label: raw})
    ]
}

# Compound the weekly returns into one index that starts at one.
def compound-index []: table -> table {
    reduce --fold {index: 1.0, rows: []} {|row, state|
        let index = ($state.index * (1 + $row.market_return))
        let rows = [...$state.rows ($row | insert market_index $index)]

        {index: $index, rows: $rows}
    }
    | get rows
}

# Build the equal-weight market series: the mean weekly return, the asset count, and the index.
export def market-series [prices]: nothing -> table {
    $prices
    | polars group-by week
    | polars agg [
        (polars col return | polars mean | polars as market_return)
        (polars col name | polars count | polars as assets)
    ]
    | polars sort-by week
    | polars collect
    | polars into-nu
    | compound-index
}

# Format a fraction as a percent text.
def percent-text []: float -> string {
    let value = $in

    $"($value * 100 | round-text 2)%"
}

# Return the within-asset autocorrelation of the weekly return at one lag.
def panel-autocorrelation [prices, lag: int]: nothing -> float {
    let asset_mean = polars col return | polars mean | polars over (polars col name)
    let centered_return = (polars col return) - $asset_mean | polars as centered
    let lagged_return = (
        (polars col centered | polars shift $lag | polars over (polars col name)) | polars as lagged
    )

    let cross_sum = (
        (polars col centered) * (polars col lagged)
        | polars sum
        | polars as cross_sum
    )

    let square_sum = (
        (polars col centered) * (polars col centered) | polars sum | polars as square_sum
    )

    let has_lagged = polars col lagged | polars is-not-null

    let sums = (
        $prices
        | polars with-column $centered_return
        | polars with-column $lagged_return
        | polars filter $has_lagged
        | polars select [$cross_sum $square_sum]
        | one-row
    )

    $sums.cross_sum / $sums.square_sum
}

# Return the Pearson correlation expression over the paired moment columns.
def correlation-expression []: nothing -> any {
    let covariance = (
        (polars col mean_return_product) - (polars col mean_return) * (polars col mean_market_return)
    )

    let return_variance = (
        (polars col mean_square_return) - (polars col mean_return) * (polars col mean_return)
    )

    let market_variance = (
        (polars col mean_square_market_return)
        - (polars col mean_market_return) * (polars col mean_market_return)
    )

    let spread = $return_variance * $market_variance | polars math sqrt

    (($covariance / $spread) | polars as correlation)
}

# Summarize the market return, the autocorrelations, and the correlation of the items with the market.
export def market-dynamics [prices, market: table, --min-weeks: int]: nothing -> table {
    let min_weeks = $min_weeks | default (load-params).eda.item_min_weeks | into int
    let has_enough_weeks = ((polars col n_weeks) >= $min_weeks)
    let returns = $market | get market_return
    let lags = 1..4

    let market_frame = (
        $market | select week market_return | polars into-df
        | polars with-column (polars col week | polars cast date | polars as week)
        | polars collect
    )

    let moments = (
        $prices
        | polars join $market_frame week week --inner
        | polars group-by name
        | polars agg [
            (polars len | polars as n_weeks)
            (polars col return | polars mean | polars as mean_return)
            (polars col market_return | polars mean | polars as mean_market_return)
            (
                (polars col return) * (polars col market_return)
                | polars mean
                | polars as mean_return_product
            )
            (
                (polars col return) * (polars col return)
                | polars mean
                | polars as mean_square_return
            )
            (
                (polars col market_return) * (polars col market_return)
                | polars mean
                | polars as mean_square_market_return
            )
        ]
        | polars filter $has_enough_weeks
    )

    let correlations = (
        $moments
        | polars with-column (correlation-expression)
        | polars select correlation
        | polars collect
        | polars into-nu
        | get correlation
        | compact
    )

    let market_metrics = {
        market_mean_return: ($returns | math avg | percent-text)
        market_std_return: ($returns | math stddev | percent-text)
    }

    let market_lag_metrics = (
        $lags
        | reduce --fold {} {|lag, metrics|
            $metrics | insert $"market_lag_($lag)" (autocorrelation $returns $lag | number-text)
        }
    )

    let asset_lag_metrics = (
        $lags
        | reduce --fold {} {|lag, metrics|
            let value = panel-autocorrelation $prices $lag | number-text

            $metrics | insert $"asset_lag_($lag)" $value
        }
    )

    let correlation_metrics = {
        mean_market_correlation: ($correlations | math avg | number-text)
        median_market_correlation: ($correlations | math median | number-text)
    }

    [
        $market_metrics
        $market_lag_metrics
        $asset_lag_metrics
        $correlation_metrics
    ]
    | reduce {|metrics, all| $all | merge $metrics }
    | metrics-from
}

# Return the correlation of the paired moments, or null when fewer than two pairs exist.
def pair-correlation [pairs: record]: nothing -> oneof<float, nothing> {
    if $pairs.n_pairs < 2 { return null }

    let covariance = ($pairs.mean_product - $pairs.mean_return * $pairs.mean_source_return)
    let return_variance = ($pairs.mean_square_return - $pairs.mean_return ** 2)
    let source_variance = (
        $pairs.mean_square_source_return - $pairs.mean_source_return ** 2
    )

    let spread = $return_variance * $source_variance | math sqrt

    $covariance / $spread
}

# Compare one source close with the main price: week share, median price ratio, and return correlation.
def source-row [prices, spec: record]: nothing -> record {
    let column = $spec.column
    let is_observed = ((polars col observed) == 1)
    let has_source_return = polars col source_return | polars is-not-null
    let observed = $prices | polars filter $is_observed
    let previous_source = polars col $column | polars shift 1 | polars over (polars col name)
    let source_ratio = ((polars col $column) / $previous_source)
    let source_return = (winsorize-return ($source_ratio - 1))

    let totals = (
        $observed
        | polars select [
            (polars len | polars as rows)
            (polars col $column | polars count | polars as source_rows)
            ((polars col price) / (polars col $column) | polars median | polars as median_ratio)
        ]
        | one-row
    )

    let pairs = (
        $prices
        | polars with-column ($source_return | polars as source_return)
        | polars filter ($is_observed and $has_source_return)
        | polars select [
            (polars len | polars as n_pairs)
            (polars col return | polars mean | polars as mean_return)
            (polars col source_return | polars mean | polars as mean_source_return)
            (
                (polars col return) * (polars col source_return)
                | polars mean
                | polars as mean_product
            )
            (
                (polars col return) * (polars col return)
                | polars mean
                | polars as mean_square_return
            )
            (
                (polars col source_return) * (polars col source_return)
                | polars mean
                | polars as mean_square_source_return
            )
        ]
        | one-row
    )

    let correlation = (pair-correlation $pairs)

    {
        source: $spec.label
        week_share: (
            if $totals.rows == 0 { null } else { $totals.source_rows / $totals.rows }
        )
        median_ratio: $totals.median_ratio
        return_correlation: $correlation
        pairs: $pairs.n_pairs
    }
}

# Compare the main price with the Steam and BUFF weekly closes.
export def source-comparison [prices]: nothing -> table {
    let is_expensive = ((polars col price) >= 800)
    let expensive = $prices | polars filter $is_expensive

    [
        (source-row $prices {column: composite_close, label: composite})
        (source-row $expensive {column: composite_close, label: composite_800})
        (source-row $prices {column: buff_close, label: buff})
    ]
}

# Group the item-weeks by the number of days with a Steam 24-hour price.
export def activity-summary [prices]: nothing -> table {
    let buckets = [
        {label: "0", upper: 0}
        {label: "1-2", upper: 2}
        {label: "3-4", upper: 4}
        {label: "5-6", upper: 6}
        {label: "7", upper: null}
    ]

    let active_bucket = (
        bucket-expression active_days active_bucket --buckets $buckets --compare {|column, upper|
            (polars col $column) <= $upper
        }
    )

    let counts = (
        $prices
        | polars with-column $active_bucket
        | polars group-by active_bucket
        | polars agg [(polars len | polars as item_weeks)]
        | polars collect
        | polars into-nu
    )

    $buckets
    | get label
    | each {|bucket|
        let found = $counts | where active_bucket == $bucket

        {
            active_bucket: $bucket
            item_weeks: (if ($found | is-empty) { 0 } else { $found | first | get item_weeks })
        }
    }
}
