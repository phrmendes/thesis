use ./output.nu [msg]

# Return the sorted unique days with a day number that starts at one.
export def day-index []: any -> any {
    let prices = $in

    $prices
    | polars select date
    | polars unique
    | polars sort-by date
    | polars collect
    | polars into-nu
    | enumerate
    | each {|row| {date: $row.item.date, day_number: ($row.index + 1)} }
    | polars into-df
    | polars with-column (polars col date | polars cast date | polars as date)
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
