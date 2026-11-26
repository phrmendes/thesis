use ./parameters.nu [load-parameters]

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
export def raise-error [message: string, culprit, --label: string = "error"] {
    error make {
        msg: $message
        label: {
            text: $label
            span: (metadata $culprit).span
        }
    }
}

# Run a command and retry it with a growing wait. Stop after the given attempts.
export def retry-action [attempts: int, action: closure] {
    for attempt in 1..$attempts {
        try { return (do $action) } catch {|err|
            if $attempt == $attempts {
                raise-error $err.msg $attempt --label "request"
            }

            let wait = 1sec * $attempt

            sleep $wait
        }
    }
}

# Winsorize one expression at the return cap bounds. The cap defaults to clean.return_cap.
export def winsorize-return [value, --cap: float] {
    let cap = $cap | default (load-parameters).clean.return_cap | into float
    let lower = (0 - $cap)

    polars when ($value < $lower) $lower
    | polars when ($value > $cap) $cap
    | polars otherwise $value
}

# Collect a frame to its first row as a record.
export def get-first-row []: any -> record {
    polars collect | polars into-nu | first
}
