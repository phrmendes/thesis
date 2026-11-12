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
const NOTEBOOK_OUTPUT_DIR = (path self | path dirname | path dirname | path join "output" "notebooks")
const NOTEBOOKS = [
    {name: "data_quality"}
    {name: "returns"}
    {name: "market"}
    {name: "calendar_effects"}
    {name: "evaluation"}
    {name: "portfolios"}
    {name: "sensitivity"}
]
const AUDIT_PATH = "files/audit.parquet"
const ASSETS_PATH = "files/assets.parquet"
const PORTFOLIO_PATH = "files/portfolio.parquet"
const BUY_AND_HOLD_PATH = "files/buy_and_hold.parquet"
const SENSITIVITY_DIR = "files/sensitivity"
const TABLES_DIR = "output/tables"
const IMAGES_DIR = "output/images"

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

    if ($summary.gaps | is-not-empty) {
        msg --level warn $"Gap days \(($summary.gaps | length)\): ($summary.gaps | str join ' ')"
    }

    if $summary.failed > 0 {
        let failed_days = $summary.failures | str join ' '

        fail $"($summary.failed) snapshot downloads failed: ($failed_days)" $failed_days --label "failed days"
    }

    msg --level done $"Fetched ($summary.fetched), skipped ($summary.skipped), failed ($summary.failed)"

    if $force or (not ($ITEMS_PATH | path exists)) {
        fetch-items

        msg --level done $"Written ($ITEMS_PATH)"
    }
}

# Build the cleaned daily prices from the raw snapshots.
export def --env "main data clean" [
    --raw-dir: path = $RAW_DIR  # Folder with the raw snapshots.
    --output: path = $PRICES_PATH  # Path of the cleaned daily prices.
    --raw  # Delete the raw snapshots after the cleaned tables save.
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    debug-mode $debug

    let files = (snapshot-files $raw_dir)

    if ($files | is-empty) {
        fail $"no snapshots in ($raw_dir): run 'thesis data fetch' first" $raw_dir --label "raw directory"
    }

    let snapshots = $files | timed "load snapshots" --step 1 --of 6 {|files| load-snapshots $files }
    let stages = (clean-stages $snapshots)

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

    if $raw {
        try {
            rm --force ...$files
        } catch {|err|
            msg --level warn $"Could not remove the raw snapshots: ($err.msg)"
        }
    }

    msg --level done $"Built ($output) with ($rows) rows"
}

# Rebuild the cleaned prices for each sensitivity variant, then summarize them in the sensitivity notebook.
export def --env "main sensitivity" [
    --raw-dir: path = $RAW_DIR  # Folder with the raw snapshots.
    --output-dir: path = $SENSITIVITY_DIR  # Folder for the cleaned table of each variant.
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    debug-mode $debug

    let files = (snapshot-files $raw_dir)

    if ($files | is-empty) {
        fail $"no snapshots in ($raw_dir): run 'thesis data fetch' first" $raw_dir --label "raw directory"
    }

    let params = (load-params)
    let variants = $params.sensitivity.variants
    let total = $variants | length
    let snapshots = (load-snapshots $files)
    let items = (items-rarity)

    mkdir $output_dir

    for entry in ($variants | enumerate) {
        let variant = $entry.item
        let min_observations = $variant.min_observations? | default $params.clean.min_observations | into int
        let min_day_share = $variant.min_day_share? | default $params.clean.min_day_share | into float
        let max_gap_days = $variant.max_gap_days? | default $params.clean.max_gap_days | into int
        let return_cap = $variant.return_cap? | default $params.clean.return_cap | into float
        let path = $output_dir | path join $"($variant.name).parquet"

        $variant | timed $"variant ($variant.name)" --step ($entry.index + 1) --of $total {|_|
            let stages = (clean-stages $snapshots --min-observations $min_observations --min-day-share $min_day_share)

            cleaned-prices $stages --items $items --max-gap-days $max_gap_days --return-cap $return_cap
            | polars collect
            | save-table $path
        }
    }

    python ($NOTEBOOKS_DIR | path join "sensitivity.py") --directory $output_dir --tables $TABLES_DIR
}

# Run the notebooks and save each one with its code and results as output/notebooks/<name>.ipynb. It needs the pipeline outputs. The draft runs in the notebooks folder so the helpers import.
export def --env "main render" [
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    debug-mode $debug

    mkdir $NOTEBOOK_OUTPUT_DIR

    for notebook in $NOTEBOOKS {
        let source = $NOTEBOOKS_DIR | path join $"($notebook.name).py"
        let draft = $NOTEBOOKS_DIR | path join $"render-($notebook.name).ipynb"

        $notebook.name | timed $"render ($notebook.name)" {|name|
            jupytext --to ipynb --output $draft $source
            jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=1800 --output $name --output-dir $NOTEBOOK_OUTPUT_DIR $draft
            rm --force $draft
        }
    }

    msg --level done $"Written ($NOTEBOOK_OUTPUT_DIR)"
}

# Run the five analysis notebooks in theme order: data quality, returns, market, calendar effects, and evaluation.
export def "main eda" [
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    debug-mode $debug

    let prices_text = $PRICES_PATH | into string
    let assets_text = $ASSETS_PATH | into string
    let audit_text = $AUDIT_PATH | into string
    let tables_text = $TABLES_DIR | into string
    let images_text = $IMAGES_DIR | into string
    let common = ["--prices" $prices_text "--tables" $tables_text]

    let with_images = [...$common "--images" $images_text]

    let notebooks = [
        {
            name: "data_quality"
            flags: [...$with_images "--assets" $assets_text "--audit" $audit_text]
        }
        {
            name: "returns"
            flags: $with_images
        }
        {
            name: "market"
            flags: $with_images
        }
        {
            name: "calendar_effects"
            flags: $common
        }
        {
            name: "evaluation"
            flags: $common
        }
    ]

    for notebook in $notebooks {
        python ($NOTEBOOKS_DIR | path join $"($notebook.name).py") ...$notebook.flags
    }
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

    python ($NOTEBOOKS_DIR | path join "portfolios.py") --prices $PRICES_PATH --k $k --rank $rank ...$flags --buy-and-hold $BUY_AND_HOLD_PATH --output $PORTFOLIO_PATH --tables $TABLES_DIR --images $IMAGES_DIR
}

# Print the Nushell completion for the commands.
export def "main completions" []: nothing -> nothing {
    let commands = scope commands | where name starts-with "main "
    let text = (extern-text $commands)

    print $text
}
