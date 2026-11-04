use ./constants.nu [PRICES_PATH]
use ./helpers.nu [winsorize-return fail week-seasons]
use ./output.nu [msg]
use ./params.nu [load-params]
use ./stats.nu [week-index weekly-raw-return]

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

# Add the week to the positive daily prices.
def add-week [raw] {
    let has_price = ((polars col price | polars is-not-null) and ((polars col price) > 0))

    $raw
    | polars filter $has_price
    | polars with-column (polars col date | polars truncate 1w | polars as week)
}

# Mark the weeks as training or testing.
def add-periods []: any -> any {
    let weeks = $in
    let total = $weeks | polars into-nu | length
    let params = (load-params)
    let return_weeks = $total - 1
    let training_weeks = $return_weeks * $params.clean.training_share | math floor
    let training_end = 1 + $training_weeks

    $weeks
    | polars with-column (
        polars when ((polars col week_number) <= $training_end) "training"
        | polars otherwise "testing"
        | polars as period
    )
}

# Keep the assets with enough positive daily prices in the training weeks.
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

# Split the raw prices into the stages that the cleaning and the audit share.
export def clean-stages [raw, --min-mean-price: float, --min-observations: int]: nothing -> record {
    let params = (load-params)
    let min_mean_price = $min_mean_price | default $params.clean.min_mean_price | into float
    let min_observations = $min_observations | default $params.clean.min_observations | into int

    let daily = (
        add-week $raw
        | polars select name date price steam_24h week
        | polars collect
    )

    let weeks = $daily | week-index
    let periods = $weeks | add-periods

    let is_training = ((polars col period) == "training")
    let training = (
        $daily
        | polars join $periods week week --inner
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
        $raw
        | polars with-column (polars col date | polars truncate 1w | polars as week)
        | polars with-column (((polars col price | polars is-not-null)) and ((polars col price) > 0) | polars as positive)
        | polars join $is_selected name name --left
        | polars join $is_valid [name date] [name date] --left
        | polars with-column (
            polars when ($is_positive and (polars col selected | polars is-not-null)) true
            | polars otherwise false
            | polars as selected
        )
        | polars with-column (
            polars when ((polars col valid | polars is-null)) false
            | polars otherwise (polars col valid)
            | polars as valid
        )
        | polars select name date week price steam_24h positive selected valid
    )

    {
        raw: $raw
        min_mean_price: $min_mean_price
        min_observations: $min_observations
        daily: $daily
        weeks: $weeks
        periods: $periods
        training: $training
        selected: $selected
        valid: $valid
        audit: $audit
    }
}

# Keep the last valid daily price of each week.
def weekly-closes []: any -> any {
    polars sort-by name week date
    | polars group-by [name week]
    | polars agg [
        (polars col price | polars last | polars as close)
    ]
}

# Keep the last positive price of one source column in each week. No bounds, no fill.
def source-closes [column: string, output: string]: any -> any {
    let prices = $in
    let has_price = ((polars col $column) > 0)

    $prices
    | polars filter $has_price
    | polars with-column (polars col date | polars truncate 1w | polars as week)
    | polars sort-by name week date
    | polars group-by [name week]
    | polars agg [
        (polars col $column | polars last | polars as $output)
    ]
}

# Count the days of each week with a Steam 24-hour price. Use it as a liquidity proxy.
def active-days []: any -> any {
    let prices = $in
    let has_steam_price = ((polars col steam_24h) > 0)

    $prices
    | polars with-column (
        polars when $has_steam_price 1
        | polars otherwise 0
        | polars as active
    )
    | polars group-by [name week]
    | polars agg [
        (polars col active | polars sum | polars as active_days)
    ]
}

# Complete every selected asset over every week and forward fill the last close.
def fill-weekly-grid [selected, weeks]: any -> any {
    let closes = $in
    let observed_weeks = $closes | polars join $weeks week week --inner
    let is_filled = polars col filled | polars is-not-null

    $selected
    | polars join $weeks --cross
    | polars join $closes [name week] [name week] --left
    | polars with-column (
        polars when ((polars col close | polars is-null)) 0
        | polars otherwise 1
        | polars as observed
    )
    | polars with-column (
        polars when ((polars col close | polars is-null)) 0
        | polars otherwise (polars col week_number)
        | polars cumulative max
        | polars over (polars col name)
        | polars as anchor
    )
    | polars join (
        $observed_weeks
        | polars select name week_number close
        | polars rename [week_number close] [anchor filled]
    ) [name anchor] [name anchor] --left
    | polars sort-by name week
    | polars filter $is_filled
    | polars with-column (((polars col week_number) - (polars col anchor)) | polars as stale)
}

# Add the weekly returns and drop the rows that are stale for too long.
def add-weekly-return []: any -> any {
    let max_stale = (load-params).clean.max_stale_weeks | into int
    let has_return = polars col return | polars is-not-null
    let is_recent = ((polars col stale) <= $max_stale)
    let follows_recent = ((polars col previous_stale) <= $max_stale)

    $in
    | polars with-column (weekly-raw-return filled | polars as raw_return)
    | polars with-column (winsorize-return (polars col raw_return) | polars as return)
    | polars with-column (
        polars col stale
        | polars shift 1
        | polars over (polars col name)
        | polars as previous_stale
    )
    | polars filter ($has_return and $is_recent and $follows_recent)
}

# Add the rarity, the period, and the sale season.
def attach-metadata [stages: record, items]: any -> any {
    let weekly = $in

    let with_rarity = (
        if ($items | describe) == "nothing" {
            $weekly | polars with-column (polars lit "" | polars as rarity)
        } else {
            $weekly | polars join $items name name --left
        }
    )

    let seasons = (
        ($stages.weeks | polars select week | polars collect | polars into-nu)
        | week-seasons
        | polars into-df
        | polars with-column (polars col week | polars cast date | polars as week)
        | polars collect
    )

    $with_rarity
    | polars join $seasons week week --left
    | polars join ($stages.periods | polars select week period) week week --left
    | polars select [
        name
        rarity
        week
        period
        filled
        return
        raw_return
        sale_season
        observed
        active_days
        composite_close
        buff_close
    ]
    | polars rename filled price
    | polars sort-by name week
}

# Build cleaned weekly prices from the raw daily prices.
export def cleaned-prices [stages: record, --items: any = null] {
    msg --level debug "clean: liquidity proxy"

    let activity = $stages.valid | active-days

    msg --level debug "clean: weekly grid and returns"

    let weekly = (
        $stages.valid
        | weekly-closes
        | fill-weekly-grid $stages.selected $stages.weeks
        | add-weekly-return
        | polars join $activity [name week] [name week] --left
        | polars join ($stages.raw | source-closes composite_price composite_close | polars collect) [name week] [name week] --left
        | polars join ($stages.raw | source-closes buff_price buff_close | polars collect) [name week] [name week] --left
    )

    msg --level debug "clean: context"

    $weekly | attach-metadata $stages $items
}

# Build one row per raw asset with its history and the selection result.
export def asset-universe [stages: record]: nothing -> any {
    let history = (
        $stages.daily
        | polars group-by name
        | polars agg [
            (polars col week | polars min | polars as first_week)
            (polars col week | polars max | polars as last_week)
            (polars col week | polars n-unique | polars as positive_weeks)
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
