use ./constants.nu [PRICES_PATH]
use ./helpers.nu [date-seasons fail winsorize-return]
use ./output.nu [msg]
use ./params.nu [load-params]
use ./stats.nu [day-index]

# Open one parquet table written by a data command.
export def load-table [path: path, command: string] {
    if not ($path | path exists) {
        fail $"missing table ($path): run '($command)' first" $path --label "table"
    }

    msg --level debug $"load table ($path)"

    polars open $path --eager
}

# Load the raw snapshots and concatenate them. One file needs no concatenation.
export def load-snapshots [files: list<path>]: nothing -> any {
    let frames = $files | each {|file| polars open $file }

    if ($frames | length) == 1 { return ($frames | first) }

    $frames | first | polars concat ...($frames | skip 1)
}

# Open the cleaned prices table.
export def load-prices [path: path = $PRICES_PATH] {
    load-table $path "data clean"
}

# Keep the positive daily prices. The daily price is the Steam 24-hour sale average.
def positive-daily [raw]: nothing -> any {
    let has_price = ((polars col price | polars is-not-null) and ((polars col price) > 0))

    $raw
    | polars filter $has_price
    | polars select name date price
    | polars collect
}

# Find the days with enough positive prices. A day below the share of the median day is a broken snapshot.
def usable-days [daily, share: float]: nothing -> any {
    let counts = (
        $daily
        | polars group-by date
        | polars agg [(polars len | polars as day_count)]
    )

    let threshold = (
        $counts
        | polars select (polars col day_count | polars median | polars as median_count)
        | polars into-nu
        | first
        | get median_count
        | into float
    ) * $share

    let is_usable = ((polars col day_count) >= $threshold)

    $counts
    | polars filter $is_usable
    | polars select date
    | polars with-column (polars lit true | polars as usable)
}

# Mark the days as training or testing.
def add-periods []: any -> any {
    let days = $in
    let total = $days | polars into-nu | length
    let params = (load-params)
    let return_days = $total - 1
    let training_days = $return_days * $params.clean.training_share | math floor
    let training_end = 1 + $training_days

    $days
    | polars with-column (
        polars when ((polars col day_number) <= $training_end) "training"
        | polars otherwise "testing"
        | polars as period
    )
}

# Keep the assets with enough positive daily prices in the training days.
def select-assets [--min-mean-price: float, --min-observations: int]: any -> any {
    let prices = $in
    let is_expensive_enough = ((polars col mean_price) >= $min_mean_price)
    let is_observed_enough = ((polars col observations) >= $min_observations)

    $prices
    | polars group-by name
    | polars agg [
        (polars col price | polars mean | polars as mean_price)
        (polars col price | polars count | polars as observations)
    ]
    | polars filter ($is_expensive_enough and $is_observed_enough)
    | polars select name
}

# Keep the daily prices inside the reference price bounds.
def valid-daily-prices [selected, training]: any -> any {
    let daily = $in
    let params = (load-params)

    let reference = (
        $training
        | polars join $selected name name --inner
        | polars group-by name
        | polars agg [(polars col price | polars median | polars as reference_price)]
    )

    let min_multiple = $params.clean.min_price_multiple | into float
    let max_multiple = $params.clean.max_price_multiple | into float
    let above_floor = (
        (polars col price) >= ((polars col reference_price) * $min_multiple)
    )
    let below_ceiling = (
        (polars col price) <= ((polars col reference_price) * $max_multiple)
    )

    $daily
    | polars join $reference name name --inner
    | polars filter ($above_floor and $below_ceiling)
}

# Split the raw prices into the stages that the cleaning and the audit share. The daily price is `steam_24h`.
export def clean-stages [
    raw
    --min-mean-price: float
    --min-observations: int
    --min-day-share: float
]: nothing -> record {
    let params = (load-params)
    let min_mean_price = $min_mean_price | default $params.clean.min_mean_price | into float
    let min_observations = $min_observations | default $params.clean.min_observations | into int
    let min_day_share = $min_day_share | default $params.clean.min_day_share | into float

    let prices = (
        $raw
        | polars select name date steam_24h price composite_price buff_price
        | polars rename [price steam_24h] [price_7d price]
    )

    let usable = (usable-days (positive-daily $prices) $min_day_share)
    let daily = (positive-daily $prices | polars join $usable date date --inner | polars select name date price)
    let days = $daily | day-index
    let periods = $days | add-periods

    let is_training = ((polars col period) == "training")
    let training = (
        $daily
        | polars join $periods date date --inner
        | polars filter $is_training
    )

    let selected = (
        $training
        | select-assets --min-mean-price $min_mean_price --min-observations $min_observations
    )

    let valid = ($daily | valid-daily-prices $selected $training)

    let is_valid = (
        $valid
        | polars select name date
        | polars with-column (polars lit true | polars as valid)
    )
    let is_selected = (
        $selected
        | polars select name
        | polars unique
        | polars with-column (polars lit true | polars as selected)
    )
    let is_positive = (polars col positive)
    let audit = (
        $prices
        | polars with-column (((polars col price | polars is-not-null)) and ((polars col price) > 0) | polars as positive)
        | polars join $usable date date --left
        | polars with-column (
            polars when ((polars col usable | polars is-null)) false
            | polars otherwise (polars col usable)
            | polars as usable
        )
        | polars join $is_selected name name --left
        | polars join $is_valid [name date] [name date] --left
        | polars with-column (
            polars when ($is_positive and (polars col usable) and (polars col selected | polars is-not-null)) true
            | polars otherwise false
            | polars as selected
        )
        | polars with-column (
            polars when ((polars col valid | polars is-null)) false
            | polars otherwise (polars col valid)
            | polars as valid
        )
        | polars select name date price positive usable selected valid
    )

    {
        raw: $prices
        min_mean_price: $min_mean_price
        min_observations: $min_observations
        daily: $daily
        days: $days
        periods: $periods
        training: $training
        selected: $selected
        valid: $valid
        audit: $audit
    }
}

# Keep the daily price of one source. A missing price stays out of the table.
def source-prices [column: string]: any -> any {
    let prices = $in
    let has_price = ((polars col $column) > 0)

    $prices
    | polars filter $has_price
    | polars select name date $column
}

# Add the daily return between two observed prices that are at most the gap limit apart. No price is filled.
def add-daily-return [max_gap: int, return_cap: float]: any -> any {
    let prices = $in
    let is_within_gap = ((polars col gap) <= $max_gap)

    let returns = (
        $prices
        | polars sort-by name date
        | polars with-column (polars col date | polars cast i32 | polars as date_number)
        | polars with-column (
            polars col date_number
            | polars shift 1
            | polars over (polars col name)
            | polars as previous_number
        )
        | polars with-column (
            polars col price
            | polars shift 1
            | polars over (polars col name)
            | polars as previous_price
        )
        | polars with-column (((polars col date_number) - (polars col previous_number)) | polars as gap)
        | polars filter $is_within_gap
        | polars with-column (((polars col price) / (polars col previous_price) - 1) | polars as raw_return)
        | polars with-column (winsorize-return (polars col raw_return) --cap $return_cap | polars as return)
        | polars select name date raw_return return
    )

    $prices | polars join $returns [name date] [name date] --left
}

# Add the rarity, the period, and the sale season.
def attach-metadata [stages: record, items]: any -> any {
    let daily = $in

    let with_rarity = (
        if ($items | describe) == "nothing" {
            $daily | polars with-column (polars lit "" | polars as rarity)
        } else {
            $daily | polars join $items name name --left
        }
    )

    let seasons = (
        ($stages.days | polars select date | polars collect | polars into-nu)
        | date-seasons
        | polars into-df
        | polars with-column (polars col date | polars cast date | polars as date)
        | polars collect
    )

    $with_rarity
    | polars join $seasons date date --left
    | polars join ($stages.periods | polars select date period) date date --left
    | polars select [
        name
        rarity
        date
        period
        price
        return
        raw_return
        sale_season
        price_7d
        composite_price
        buff_price
    ]
    | polars sort-by name date
}

# Build the cleaned daily prices from the raw daily prices.
export def cleaned-prices [
    stages: record
    --items: any = null
    --max-gap-days: int
    --return-cap: float
]: nothing -> any {
    msg --level debug "clean: daily returns"

    let params = (load-params)
    let max_gap = $max_gap_days | default $params.clean.max_gap_days | into int
    let cap = $return_cap | default $params.clean.return_cap | into float

    let composite = ($stages.raw | source-prices composite_price | polars collect)
    let buff = ($stages.raw | source-prices buff_price | polars collect)
    let price_7d = ($stages.raw | source-prices price_7d | polars collect)

    let daily = (
        $stages.valid
        | polars select name date price
        | add-daily-return $max_gap $cap
        | polars join $price_7d [name date] [name date] --left
        | polars join $composite [name date] [name date] --left
        | polars join $buff [name date] [name date] --left
    )

    msg --level debug "clean: context"

    $daily | attach-metadata $stages $items
}

# Build one row per raw asset with its history and the selection result.
export def asset-universe [stages: record]: nothing -> any {
    let history = (
        $stages.daily
        | polars group-by name
        | polars agg [
            (polars col date | polars min | polars as first_date)
            (polars col date | polars max | polars as last_date)
            (polars col date | polars n-unique | polars as positive_days)
        ]
    )

    let training = (
        $stages.training
        | polars group-by name
        | polars agg [
            (polars col price | polars mean | polars as training_mean_price)
            (polars col price | polars count | polars as training_observations)
        ]
    )

    $history
    | polars join $training name name --left
    | polars with-column (
        polars when ((polars col training_observations | polars is-null)) "no_training_data"
        | polars when ((polars col training_observations) < $stages.min_observations) "few_observations"
        | polars when ((polars col training_mean_price) < $stages.min_mean_price) "low_price"
        | polars otherwise "selected"
        | polars as reason
    )
    | polars sort-by name
}
