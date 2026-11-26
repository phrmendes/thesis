use ./helpers.nu [raise-error winsorize-return]
use ./output.nu [print-message]
use ./parameters.nu [load-parameters]
use ./stats.nu [build-day-index]

const CLEAN_PATH = (path self)

# Check that every output exists and is newer than every input of the cleaning, including this script.
export def check-outputs-current [outputs: list<path>, inputs: list<path>]: nothing -> bool {
    if ($outputs | any {|path| not ($path | path exists) }) { return false }

    let built = $outputs | each {|path| ls $path | first | get modified } | sort | first
    let changed = (
        [...$inputs $CLEAN_PATH]
        | where ($it | path exists)
        | each {|path| ls $path | first | get modified }
        | sort
        | last
    )

    $changed <= $built
}

# Load the raw snapshots and concatenate them. One file needs no concatenation.
export def load-snapshots [files: list<path>]: nothing -> any {
    let frames = $files | each {|file| polars open $file }

    if ($frames | length) == 1 { return ($frames | first) }

    $frames | first | polars concat ...($frames | skip 1)
}

# Keep the positive daily prices. The daily price is the Steam 24-hour sale average.
def filter-positive-daily [raw]: nothing -> any {
    let has_price = ((polars col price | polars is-not-null) and ((polars col price) > 0))

    $raw
    | polars filter $has_price
    | polars select name date price
    | polars collect
}

# Find the days with enough positive prices. A day below the share of the median day is a broken snapshot.
def find-usable-days [daily, share: float]: nothing -> any {
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

# Mark consecutive dates as training, validation, and testing.
def add-periods []: any -> any {
    let days = $in
    let total = $days | polars into-nu | length
    let parameters = (load-parameters)
    let return_days = $total - 1
    let training_share = $parameters.clean.training_share | into float
    let validation_share = $parameters.clean.validation_share | into float

    if $training_share <= 0 or $validation_share <= 0 or ($training_share + $validation_share) >= 1 {
        raise-error "training and validation shares must be positive and leave testing dates" $parameters.clean --label "period shares"
    }

    let training_end = 1 + ($return_days * $training_share | math floor)
    let validation_end = 1 + ($return_days * ($training_share + $validation_share) | math floor)
    let is_training = ((polars col day_number) <= $training_end)
    let is_validation = ((polars col day_number) <= $validation_end)

    $days
    | polars with-column (
        polars when $is_training "training"
        | polars when $is_validation "validation"
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
def filter-valid-daily-prices [selected, training]: any -> any {
    let daily = $in
    let parameters = (load-parameters)

    let reference = (
        $training
        | polars join $selected name name --inner
        | polars group-by name
        | polars agg [(polars col price | polars median | polars as reference_price)]
    )

    let min_multiple = $parameters.clean.min_price_multiple | into float
    let max_multiple = $parameters.clean.max_price_multiple | into float
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
export def build-clean-stages [
    raw
    --min-mean-price: float
    --min-observations: int
    --min-day-share: float
]: nothing -> record {
    let parameters = (load-parameters)
    let min_mean_price = $min_mean_price | default $parameters.clean.min_mean_price | into float
    let min_observations = $min_observations | default $parameters.clean.min_observations | into int
    let min_day_share = $min_day_share | default $parameters.clean.min_day_share | into float

    let prices = (
        $raw
        | polars select name date steam_24h price composite_price buff_price
        | polars rename [price steam_24h] [price_7d price]
    )

    let usable = (find-usable-days (filter-positive-daily $prices) $min_day_share)
    let daily = (
        filter-positive-daily $prices
        | polars join $usable date date --inner
        | polars select name date price
    )

    let days = $daily | build-day-index
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

    let valid = $daily | filter-valid-daily-prices $selected $training

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
        periods: $periods
        training: $training
        valid: $valid
        audit: $audit
    }
}

# Keep the daily price of one source. A missing price stays out of the table.
def filter-source-prices [column: string]: any -> any {
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

# Add the rarity and the period.
def attach-metadata [stages: record, items]: any -> any {
    let daily = $in

    let with_rarity = (
        if ($items | describe) == "nothing" {
            $daily | polars with-column (polars lit "" | polars as rarity)
        } else {
            $daily | polars join $items name name --left
        }
    )

    $with_rarity
    | polars join ($stages.periods | polars select date period) date date --left
    | polars select [
        name
        rarity
        date
        period
        price
        return
        raw_return
        price_7d
        composite_price
        buff_price
    ]
    | polars sort-by name date
}

# Build the cleaned daily prices from the raw daily prices.
export def build-cleaned-prices [
    stages: record
    --items: any = null
    --max-gap-days: int
    --return-cap: float
]: nothing -> any {
    print-message --level debug "clean: daily returns"

    let parameters = (load-parameters)
    let max_gap = $max_gap_days | default $parameters.clean.max_gap_days | into int
    let cap = $return_cap | default $parameters.clean.return_cap | into float

    let composite = $stages.raw | filter-source-prices composite_price | polars collect
    let buff = $stages.raw | filter-source-prices buff_price | polars collect
    let price_7d = $stages.raw | filter-source-prices price_7d | polars collect

    let daily = (
        $stages.valid
        | polars select name date price
        | add-daily-return $max_gap $cap
        | polars join $price_7d [name date] [name date] --left
        | polars join $composite [name date] [name date] --left
        | polars join $buff [name date] [name date] --left
    )

    print-message --level debug "clean: context"

    $daily | attach-metadata $stages $items
}

# Build one row per raw asset with its history and the selection result.
export def build-asset-universe [stages: record]: nothing -> any {
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
