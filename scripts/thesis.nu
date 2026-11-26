use ./lib/clean.nu [
    build-asset-universe
    build-clean-stages
    build-cleaned-prices
    check-outputs-current
    load-snapshots
]
use ./lib/completions.nu [build-extern-text]
use ./lib/constants.nu [ITEMS_PATH RAW_DIR]
use ./lib/fetch.nu [fetch-day fetch-items load-item-rarity list-snapshot-files summarize-statuses]
use ./lib/helpers.nu [raise-error get-first-row]
use ./lib/output.nu [set-debug-mode print-message show-progress run-timed]
use ./lib/parameters.nu [load-parameters GLOBAL_PARAMETERS_PATH PARAMETERS_PATH]
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

# Thesis pipeline for the CS:GO skin prices. Run a command with
export def main []: nothing -> nothing {
    print-message "Run `nu scripts/thesis.nu --help` to list the commands."
}

# Download CS:GO price snapshots and item metadata.
export def --env "main data fetch" [
    --start: string  # First day to fetch, as YYYY-MM-DD. Default: collection.first_date in scripts/parameters.toml.
    --end: string  # Last day to fetch, as YYYY-MM-DD. Default: collection.last_date in scripts/parameters.toml.
    --data-dir: path = $RAW_DIR  # Folder for the raw snapshots.
    --concurrency: int = $DEFAULT_CONCURRENCY  # Number of parallel downloads.
    --force  # Download again even when a snapshot is cached.
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    set-debug-mode $debug

    let collection = (load-parameters).collection
    let start = $start | default $collection.first_date
    let end = $end | default $collection.last_date

    if $start > $end {
        raise-error "start date is after end date" $start --label "date range"
    }

    try {
        mkdir $data_dir
    } catch {|err|
        raise-error $"cannot create ($data_dir): ($err.msg)" $data_dir --label "data directory"
    }

    let days = (seq date --begin-date $start --end-date $end)
    let total = $days | length

    print-message $"Fetching ($total) days into ($data_dir)"

    let results = (
        $days | chunks $FETCH_BATCH_SIZE | enumerate | each {|batch|
            let statuses = (
                $batch.item | par-each --threads $concurrency {|day|
                    let status = (fetch-day $day $data_dir --force=$force)

                    print-message --level debug $"snapshot ($day): ($status)"

                    {day: $day, status: $status}
                }
            )

            let processed = [$total (($batch.index + 1) * $FETCH_BATCH_SIZE)] | math min | into int

            show-progress $processed $total --label "days"

            $statuses
        } | flatten
    )

    let summary = (summarize-statuses $results)

    if ($summary.gaps | is-not-empty) {
        print-message --level warn $"Gap days \(($summary.gaps | length)\): ($summary.gaps | str join ' ')"
    }

    if $summary.failed > 0 {
        let failed_days = $summary.failures | str join ' '

        raise-error $"($summary.failed) snapshot downloads failed: ($failed_days)" $failed_days --label "failed days"
    }

    print-message --level done $"Fetched ($summary.fetched), skipped ($summary.skipped), failed ($summary.failed)"

    if $force or (not ($ITEMS_PATH | path exists)) {
        fetch-items

        print-message --level done $"Written ($ITEMS_PATH)"
    }
}

# Build the cleaned daily prices from the raw snapshots.
export def --env "main data clean" [
    --raw-dir: path = $RAW_DIR  # Folder with the raw snapshots.
    --output: path  # Cleaned price path. Default: paths.prices in parameters.toml.
    --raw  # Delete the raw snapshots after the cleaned tables save.
    --force  # Rebuild even when no input changed.
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    set-debug-mode $debug

    let parameters = (load-parameters)
    let output = $output | default $parameters.paths.prices
    let files = (list-snapshot-files $raw_dir)
    let outputs = [$output $parameters.paths.audit $parameters.paths.assets]

    if (not $force) and (check-outputs-current $outputs [...$files $ITEMS_PATH $GLOBAL_PARAMETERS_PATH $PARAMETERS_PATH]) {
        print-message --level done $"($output) is current: no input changed"

        return
    }

    if ($files | is-empty) {
        raise-error $"no snapshots in ($raw_dir): run 'thesis data fetch' first" $raw_dir --label "raw directory"
    }

    let snapshots = $files | run-timed "load snapshots" --step 1 --of 6 {|files| load-snapshots $files }
    let stages = (build-clean-stages $snapshots)

    let cleaned = (
        $stages
        | run-timed "build prices" --step 2 --of 6 {|stages|
            build-cleaned-prices $stages --items (load-item-rarity) | polars collect
        }
    )

    let assets = (
        $stages
        | run-timed "assets" --step 3 --of 6 {|stages| build-asset-universe $stages | polars collect }
    )

    let rows = (
        $cleaned
        | polars select (polars len | polars as rows)
        | get-first-row
        | get rows
    )

    $cleaned | run-timed "save prices" --step 4 --of 6 {|frame| $frame | save-table $output }

    $stages.audit | run-timed "save audit" --step 5 --of 6 {|frame| $frame | save-table $parameters.paths.audit }

    $assets | run-timed "save assets" --step 6 --of 6 {|frame| $frame | save-table $parameters.paths.assets }

    if $raw {
        try {
            rm --force ...$files
        } catch {|err|
            print-message --level warn $"Could not remove the raw snapshots: ($err.msg)"
        }
    }

    print-message --level done $"Built ($output) with ($rows) rows"
}

# Rebuild the cleaned prices for each sensitivity variant, then summarize them in the sensitivity notebook.
export def --env "main sensitivity" [
    --raw-dir: path = $RAW_DIR  # Folder with the raw snapshots.
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    set-debug-mode $debug

    let files = (list-snapshot-files $raw_dir)

    if ($files | is-empty) {
        raise-error $"no snapshots in ($raw_dir): run 'thesis data fetch' first" $raw_dir --label "raw directory"
    }

    let parameters = (load-parameters)
    let variants = $parameters.sensitivity_variants
    let output_dir = $parameters.paths.sensitivity
    let total = $variants | length
    let snapshots = (load-snapshots $files)
    let items = (load-item-rarity)

    mkdir $output_dir

    for entry in ($variants | enumerate) {
        let variant = $entry.item
        let min_observations = $variant.min_observations? | default $parameters.clean.min_observations | into int
        let min_day_share = $variant.min_day_share? | default $parameters.clean.min_day_share | into float
        let max_gap_days = $variant.max_gap_days? | default $parameters.clean.max_gap_days | into int
        let return_cap = $variant.return_cap? | default $parameters.clean.return_cap | into float
        let path = $output_dir | path join $"($variant.name).parquet"

        $variant | run-timed $"variant ($variant.name)" --step ($entry.index + 1) --of $total {|_|
            let stages = (build-clean-stages $snapshots --min-observations $min_observations --min-day-share $min_day_share)

            build-cleaned-prices $stages --items $items --max-gap-days $max_gap_days --return-cap $return_cap
            | polars collect
            | save-table $path
        }
    }

    python ($NOTEBOOKS_DIR | path join "sensitivity.py")
}

# Run the notebooks and save each one with its code and results as output/notebooks/<name>.ipynb. It needs the pipeline outputs. The draft runs in the notebooks folder so the helpers import.
export def --env "main render" [
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    set-debug-mode $debug

    mkdir $NOTEBOOK_OUTPUT_DIR

    for notebook in $NOTEBOOKS {
        let source = $NOTEBOOKS_DIR | path join $"($notebook.name).py"
        let draft = $NOTEBOOKS_DIR | path join $"render-($notebook.name).ipynb"

        $notebook.name | run-timed $"render ($notebook.name)" {|name|
            jupytext --to ipynb --output $draft $source
            jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=1800 --output $name --output-dir $NOTEBOOK_OUTPUT_DIR $draft
            rm --force $draft
        }
    }

    print-message --level done $"Written ($NOTEBOOK_OUTPUT_DIR)"
}

# Run the five analysis notebooks in theme order: data quality, returns, market, calendar effects, and evaluation.
export def "main eda" [
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    set-debug-mode $debug

    for notebook in [data_quality returns market calendar_effects evaluation] {
        python ($NOTEBOOKS_DIR | path join $"($notebook).py")
    }
}

# Build an equal-weight buy-and-hold portfolio with the configured strategy.
export def --env "main portfolio buy-and-hold" [
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    set-debug-mode $debug

    python ($NOTEBOOKS_DIR | path join "portfolios.py")
}

# Print the Nushell completion for the commands.
export def "main completions" []: nothing -> nothing {
    let commands = scope commands | where name starts-with "main "
    let text = (build-extern-text $commands)

    print $text
}
