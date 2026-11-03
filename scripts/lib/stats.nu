use ./output.nu [msg]

# Return the ratio between the current and the previous weekly price.
def weekly-ratio [column: string]: nothing -> any {
    let previous = polars col $column | polars shift 1 | polars over (polars col name)

    (polars col $column) / $previous
}

# Return the uncapped weekly return expression for one price column.
export def weekly-raw-return [column: string]: nothing -> any {
    (weekly-ratio $column) - 1
}

# Count the rows that meet one condition. Return the expression.
export def count-where [condition]: nothing -> any {
    polars when ($condition) 1
    | polars otherwise 0
    | polars sum
}

# Return the Sharpe ratio expression.
export def sharpe [mean_column: string, std_column: string]: nothing -> any {
    (polars col $mean_column) / (polars col $std_column)
}

# Return the Sortino ratio expression: the mean over the standard deviation of the negative weeks.
export def sortino [mean_column: string, negative_std_column: string]: nothing -> any {
    (polars col $mean_column) / (polars col $negative_std_column)
}

# Return the sorted unique weeks with a week number that starts at one.
export def week-index []: any -> any {
    let prices = $in

    $prices
    | polars select week
    | polars unique
    | polars sort-by week
    | polars collect
    | polars into-nu
    | enumerate
    | each {|row| {week: $row.item.week, week_number: ($row.index + 1)} }
    | polars into-df
    | polars with-column (polars col week | polars cast date | polars as week)
    | polars collect
}

# Save one frame as parquet and create the parent directory.
export def save-table [path: path]: any -> string {
    let frame = $in

    msg --level debug $"save ($path)"

    mkdir (($path | path parse).parent)

    if (($frame | describe) | str starts-with "polars_") {
        return ($frame | polars save $path)
    }

    $frame | polars into-df | polars save $path
}

# Return the sample standard deviation, or null when fewer than two values exist.
export def sample-std [values: list<any>]: nothing -> oneof<float, nothing> {
    if ($values | length) < 2 { return null }

    $values | math stddev --sample
}

# Divide one number by another, or return null when the denominator is null or not positive.
export def safe-ratio [numerator: oneof<float, nothing>, denominator: oneof<float, nothing>]: nothing -> oneof<float, nothing> {
    if $denominator == null { return null }

    let divisor: float = $denominator | into float

    if $divisor <= 0 { return null }

    if $numerator == null { return null }

    let dividend: float = $numerator | into float

    $dividend / $divisor
}

# Return the aggregation expressions for the raw moments of one column.
export def moment-expressions [column: string]: nothing -> list<any> {
    let value = (polars col $column)

    [
        ($value | polars mean | polars as m1)
        (($value * $value) | polars mean | polars as m2)
        (($value * $value * $value) | polars mean | polars as m3)
        (($value * $value * $value * $value) | polars mean | polars as m4)
    ]
}

# Compute the skewness and the excess kurtosis from the raw moments.
export def shape-measures [moments: record]: nothing -> record {
    let mean = $moments.m1
    let variance = ($moments.m2 - $mean ** 2)
    let third_moment = ($moments.m3 - 3 * $mean * $moments.m2 + 2 * $mean ** 3)
    let fourth_moment = (
        $moments.m4 - 4 * $mean * $moments.m3 + 6 * $mean ** 2 * $moments.m2 - 3 * $mean ** 4
    )

    {
        skewness: ($third_moment / ($variance ** 1.5))
        excess_kurtosis: ($fourth_moment / ($variance ** 2) - 3)
    }
}

# Return the autocorrelation of a list at one lag.
export def autocorrelation [values: list<float>, lag: int]: nothing -> float {
    let mean = $values | math avg
    let centered = $values | each {|value| $value - $mean }
    let denominator = $centered | each {|value| $value * $value } | math sum

    let numerator = (
        $centered
        | zip ($centered | skip $lag)
        | each {|pair| $pair | math product }
        | math sum
    )

    ($numerator | into float) / ($denominator | into float)
}
