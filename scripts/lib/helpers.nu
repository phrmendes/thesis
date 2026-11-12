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

# Winsorize one expression at the return cap bounds. The cap defaults to clean.return_cap.
export def winsorize-return [value, --cap: float] {
    let cap = $cap | default (load-params).clean.return_cap | into float
    let lower = (0 - $cap)

    polars when ($value < $lower) $lower
    | polars when ($value > $cap) $cap
    | polars otherwise $value
}

# Return the sale season of one day, or "none".
export def sale-season [day: datetime]: nothing -> string {
    let seasons = (
        (load-params).sale_periods
        | where (($day >= ($it.start | into datetime)) and ($day <= ($it.end | into datetime)))
        | get season
        | sort
    )

    if ($seasons | is-empty) { return "none" }

    $seasons | first
}

# Add a sale season to every day of a table.
export def date-seasons []: table -> table {
    let days = $in

    $days | each {|row| {date: $row.date, sale_season: (sale-season $row.date)} }
}

# Collect a frame to its first row as a record.
export def one-row []: any -> record {
    polars collect | polars into-nu | first
}
