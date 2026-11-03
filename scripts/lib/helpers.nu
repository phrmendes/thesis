use ./params.nu [load-params]

# Convert one raw JSON price to a float. Return null when the value is missing or not numeric.
export def parse-price []: oneof<string, number, nothing> -> oneof<float, nothing> {
    let value = $in

    if $value == null { return null }

    if ($value | describe) == "string" {
        try { return ($value | into float) } catch { return null }
    }

    $value | into float
}

# Raise an error that points at one value of the caller. Use this for every failure message, and do not write `error make` by hand.
export def fail [message: string, culprit, --label: string = "error"] {
    error make {
        msg: $message
        label: {
            text: $label
            span: (metadata $culprit).span
        }
    }
}

# Run a command and retry it with a growing wait. Stop after the given attempts.
export def with-retry [attempts: int, action: closure] {
    for attempt in 1..$attempts {
        try { return (do $action) } catch {|err|
            if $attempt == $attempts {
                fail $err.msg $attempt --label "request"
            }

            let wait = 1sec * $attempt

            sleep $wait
        }
    }
}

# Winsorize one expression at the return cap bounds.
export def winsorize-return [value] {
    let cap = (load-params).return_cap
    let lower = (0 - $cap)

    polars when ($value < $lower) $lower
    | polars when ($value > $cap) $cap
    | polars otherwise $value
}

# Winsorize one number at the return cap bounds.
export def winsorize-number [value: float]: nothing -> float {
    let cap = (load-params).return_cap
    let lower = (0 - $cap)
    let above_floor = [$value $lower] | math max

    [$above_floor $cap] | math min
}

# Return the sale season of one week, or "none".
export def sale-season [week: datetime]: nothing -> string {
    let seasons = (
        (load-params).sale_periods
        | where not (
            ($week > ($it.end | into datetime))
            or (($week + 6day) < ($it.start | into datetime))
        )
        | get season
        | sort
    )
    if ($seasons | is-empty) { return "none" }

    $seasons | first
}

# Add a sale season to every week of a table.
export def week-seasons []: table -> table {
    let weeks = $in

    $weeks | each {|row| {week: $row.week, sale_season: (sale-season $row.week)} }
}

# Return the mean of the non-null values, or null when no value remains.
export def mean-or-null []: list<any> -> oneof<float, nothing> {
    let values = $in
    let non_null_values = $values | compact

    if ($non_null_values | is-empty) { return null }

    $non_null_values | math avg
}

# Collect a frame to its first row as a record.
export def one-row []: any -> record {
    polars collect | polars into-nu | first
}

# Format one number with a fixed number of decimals. Pad the missing zeros.
export def number-text [decimals: int = 4]: number -> string {
    into string --decimals $decimals
}

# Format one number rounded to a number of decimals. Do not pad the zeros.
export def round-text [decimals: int = 2]: number -> string {
    math round --precision $decimals | into string
}

# Return one row of a metric table. Convert the value to a string.
export def metric-row [name: string, value: oneof<string, int, float>]: nothing -> record {
    {
        metric_name: $name
        metric_value: ($value | into string)
    }
}

# Turn one record of metric names and values into the metric table.
export def metrics-from []: record -> table {
    items {|name, value| metric-row $name $value }
}

# Convert one metric table into a record keyed by the metric name.
export def metric-record []: table -> record {
    each {|row| {$row.metric_name: $row.metric_value} } | into record
}
