use ./lib/clean.nu [
    asset-universe
    clean-stages
    cleaned-prices
    load-prices
    load-snapshots
    load-table
]
use ./lib/completions.nu [extern-text]
use ./lib/constants.nu [ITEMS_PATH PRICES_PATH RAW_DIR]
use ./lib/fetch.nu [fetch-day fetch-items items-rarity snapshot-files summarize-statuses]
use ./lib/helpers.nu [fail one-row]
use ./lib/output.nu [debug-mode msg progress timed]
use ./lib/params.nu [load-params]
use ./lib/stats.nu [save-table]

const DEFAULT_CONCURRENCY = 10
const FETCH_BATCH_SIZE = 50
const NOTEBOOKS_DIR = (path self | path dirname | path dirname | path join "notebooks")
const AUDIT_PATH = "files/audit.parquet"
const ASSETS_PATH = "files/assets.parquet"
const PORTFOLIO_PATH = "files/portfolio.parquet"
const BUY_AND_HOLD_PATH = "files/buy_and_hold.parquet"
const DATASET_PATH = "files/dataset.parquet"
const PREDICTIONS_PATH = "files/predictions.parquet"
const TABLES_DIR = "tex/tables"
const IMAGES_DIR = "images"

# Thesis pipeline for the CS:GO skin prices. Run a command with
export def main []: nothing -> nothing {
    msg "Run `nu scripts/thesis.nu --help` to list the commands."
}

# Download CS:GO price snapshots and item metadata.
export def --env "main data fetch" [
    --start: string  # First day to fetch, as YYYY-MM-DD. Default: collection.first_date in params.toml.
    --end: string  # Last day to fetch, as YYYY-MM-DD. Default: collection.last_date in params.toml.
    --data-dir: path = $RAW_DIR  # Folder for the raw snapshots.
    --concurrency: int = $DEFAULT_CONCURRENCY  # Number of parallel downloads.
    --force  # Download again even when a snapshot is cached.
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    debug-mode $debug

    let collection = (load-params).collection
    let start = $start | default $collection.first_date
    let end = $end | default $collection.last_date

    if $start > $end {
        fail "start date is after end date" $start --label "date range"
    }

    try {
        mkdir $data_dir
    } catch {|err|
        fail $"cannot create ($data_dir): ($err.msg)" $data_dir --label "data directory"
    }

    let days = (seq date --begin-date $start --end-date $end)
    let total = $days | length

    msg $"Fetching ($total) days into ($data_dir)"

    let results = (
        $days | chunks $FETCH_BATCH_SIZE | enumerate | each {|batch|
            let statuses = (
                $batch.item | par-each --threads $concurrency {|day|
                    let status = (fetch-day $day $data_dir --force=$force)

                    msg --level debug $"snapshot ($day): ($status)"

                    {day: $day, status: $status}
                }
            )

            let processed = [$total (($batch.index + 1) * $FETCH_BATCH_SIZE)] | math min | into int

            progress $processed $total --label "days"

            $statuses
        } | flatten
    )

    let summary = (summarize-statuses $results)

    msg --level done $"Fetched ($summary.fetched), skipped ($summary.skipped), failed ($summary.failed)"

    if ($summary.gaps | is-not-empty) {
        msg --level warn $"Gap days \(($summary.gaps | length)\): ($summary.gaps | str join ' ')"
    }

    if $summary.failed > 0 {
        msg --level warn $"Failed days: ($summary.failures | str join ' ')"
    }

    if $force or (not ($ITEMS_PATH | path exists)) {
        fetch-items

        msg --level done $"Written ($ITEMS_PATH)"
    }
}

# Build the cleaned weekly prices from the raw snapshots.
export def --env "main data clean" [
    --raw-dir: path = $RAW_DIR  # Folder with the raw snapshots.
    --output: path = $PRICES_PATH  # Path of the cleaned weekly prices.
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    debug-mode $debug

    let files = (snapshot-files $raw_dir)

    if ($files | is-empty) {
        fail $"no snapshots in ($raw_dir): run 'thesis data fetch' first" $raw_dir --label "raw directory"
    }

    let raw = $files | timed "load snapshots" --step 1 --of 6 {|files| load-snapshots $files }
    let stages = (clean-stages $raw)

    let cleaned = (
        $stages
        | timed "build prices" --step 2 --of 6 {|stages|
            cleaned-prices $stages --items (items-rarity) | polars collect
        }
    )

    let assets = (
        $stages
        | timed "assets" --step 3 --of 6 {|stages| asset-universe $stages | polars collect }
    )

    let rows = (
        $cleaned
        | polars select (polars len | polars as rows)
        | one-row
        | get rows
    )

    $cleaned | timed "save prices" --step 4 --of 6 {|frame| $frame | save-table $output }

    $stages.audit | timed "save audit" --step 5 --of 6 {|frame| $frame | save-table $AUDIT_PATH }

    $assets | timed "save assets" --step 6 --of 6 {|frame| $frame | save-table $ASSETS_PATH }

    try {
        rm --force ...$files
    } catch {|err|
        msg --level warn $"Could not remove the raw snapshots: ($err.msg)"
    }

    msg --level done $"Built ($output) with ($rows) rows"
}

# Run the EDA notebook: calculate, display, and export the tables and the charts.
export def "main eda" [
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    debug-mode $debug

    let prices_text = $PRICES_PATH | into string
    let assets_text = $ASSETS_PATH | into string
    let audit_text = $AUDIT_PATH | into string
    let tables_text = $TABLES_DIR | into string
    let images_text = $IMAGES_DIR | into string

    python ($NOTEBOOKS_DIR | path join "eda.py") --prices $prices_text --assets $assets_text --audit $audit_text --tables $tables_text --images $images_text
}

# Build an equal-weight buy-and-hold portfolio.
export def --env "main portfolio buy-and-hold" [
    --k: int  # Number of assets in the portfolio. Required.
    --rank: string = "roi"  # Training ratio that orders the assets: roi, sharpe or sortino.
    --roi: float  # Minimum training ROI. Default: portfolio.min_roi in params.toml.
    --sharpe: float  # Minimum training Sharpe ratio. Default: portfolio.min_sharpe in params.toml.
    --sortino: float  # Minimum training Sortino ratio. Default: portfolio.min_sortino in params.toml.
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    debug-mode $debug

    let flags = (
        {roi: $roi, sharpe: $sharpe, sortino: $sortino}
        | transpose name value
        | where value != null
        | each {|row| [$"--($row.name)" ($row.value | into string)] }
        | flatten
    )

    python ($NOTEBOOKS_DIR | path join "portfolios.py") --prices $PRICES_PATH --k $k --rank $rank ...$flags --buy-and-hold $BUY_AND_HOLD_PATH --output $PORTFOLIO_PATH --table ($TABLES_DIR | path join "portfolio.tex")
}

# Print the Nushell completion for the commands.
export def "main completions" []: nothing -> nothing {
    let commands = scope commands | where name starts-with "main "
    let text = (extern-text $commands)

    print $text
}

# Fit the CatBoost model and write the conformal predictions. This is a skeleton.
export def "main model fit" []: nothing -> nothing {
    let dataset_text = $DATASET_PATH | into string
    let output_text = $PREDICTIONS_PATH | into string

    python ($NOTEBOOKS_DIR | path join "models.py") --dataset $dataset_text --output $output_text
}
