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
