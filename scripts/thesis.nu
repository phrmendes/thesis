use ./lib/audit.nu [cleaning-audit]
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
use ./lib/eda.nu [
    activity-summary
    coverage-daily
    coverage-items
    launch-period-groups
    market-dynamics
    market-series
    quality-metrics
    return-distribution
    return-statistics
    source-comparison
]
use ./lib/fetch.nu [fetch-day fetch-items items-rarity snapshot-files summarize-statuses]
use ./lib/helpers.nu [fail metric-record one-row]
use ./lib/output.nu [debug-mode msg progress timed]
use ./lib/params.nu [load-params]
use ./lib/portfolio.nu [buy-and-hold portfolio-summary]
use ./lib/stats.nu [save-table]

const DEFAULT_CONCURRENCY = 10
const FETCH_BATCH_SIZE = 50
const FILES_DIR = "files"
const AUDIT_PATH = "files/audit.parquet"
const ASSETS_PATH = "files/assets.parquet"
const MARKET_PATH = "files/market.parquet"
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
    --start: string  # First day to fetch, as YYYY-MM-DD. Default: collection.first_date in params.nuon.
    --end: string  # Last day to fetch, as YYYY-MM-DD. Default: collection.last_date in params.nuon.
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

    let raw = $files | timed "load snapshots" --step 1 --of 7 {|files| load-snapshots $files }
    let stages = (clean-stages $raw)

    let cleaned = (
        $stages
        | timed "build prices" --step 2 --of 7 {|stages|
            cleaned-prices $stages --items (items-rarity) | polars collect
        }
    )

    let audit = $stages | timed "audit" --step 3 --of 7 {|stages| cleaning-audit $stages $cleaned }

    let assets = (
        $stages
        | timed "assets" --step 4 --of 7 {|stages| asset-universe $stages | polars collect }
    )

    let rows = (
        $cleaned
        | polars select (polars len | polars as rows)
        | one-row
        | get rows
    )

    $cleaned | timed "save prices" --step 5 --of 7 {|frame| $frame | save-table $output }

    $audit | timed "save audit" --step 6 --of 7 {|rows| $rows | save-table $AUDIT_PATH }

    $assets | timed "save assets" --step 7 --of 7 {|rows| $rows | save-table $ASSETS_PATH }

    try {
        rm --force ...$files
    } catch {|err|
        msg --level warn $"Could not remove the raw snapshots: ($err.msg)"
    }

    let summary = $audit | metric-record

    msg --level done $"Built ($output) with ($rows) rows"

    msg $"Observed share ($summary.observed_share), zero returns ($summary.zero_returns), capped returns ($summary.capped_returns)"

    msg $"Weekly jumps ($summary.weekly_jumps), reversed ($summary.reversed_jumps), bounds removed ($summary.bounds_removed_rows) daily rows"

    let last_date = ((load-params).collection.last_date)

    if $summary.last_price_day < $last_date {
        msg --level warn $"prices end at ($summary.last_price_day), before ($last_date)"
    }
}

# Build every EDA summary table.
export def --env "main eda" [
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    debug-mode $debug

    let prices = (load-prices)
    let assets = (load-table $ASSETS_PATH "thesis data clean")
    let audit = load-table $AUDIT_PATH "thesis data clean" | polars into-nu | metric-record
    let market = (market-series $prices)

    let plan = [
        {
            name: "coverage_daily"
            build: {|| coverage-daily $prices $audit }
        }
        {
            name: "coverage_items"
            build: {|| coverage-items $assets }
        }
        {
            name: "selection"
            build: {|| launch-period-groups $assets }
        }
        {
            name: "quality"
            build: {|| quality-metrics $prices }
        }
        {
            name: "returns"
            build: {|| return-statistics $prices }
        }
        {
            name: "distribution"
            build: {|| return-distribution $prices }
        }
        {
            name: "dynamics"
            build: {|| market-dynamics $prices $market }
        }
        {
            name: "market"
            build: {|| $market }
        }
        {
            name: "sources"
            build: {|| source-comparison $prices }
        }
        {
            name: "activity"
            build: {|| activity-summary $prices }
        }
    ]

    let total = $plan | length

    $plan
    | enumerate
    | each {|row|
        let table = (
            timed $row.item.name --step ($row.index + 1) --of $total {|| do $row.item.build }
        )

        $table | save-table $"($FILES_DIR)/($row.item.name).parquet"
    }

    msg --level done $"Written EDA tables in ($FILES_DIR)"
}

# Build an equal-weight buy-and-hold portfolio for one portfolio size.
export def --env "main portfolio buy-and-hold" [
    --k: int  # Number of assets in the portfolio. Required.
    --rank: string = "roi"  # Training ratio that orders the assets: roi, sharpe or sortino.
    --roi: float  # Minimum training ROI. Default: portfolio.min_roi in params.nuon.
    --sharpe: float  # Minimum training Sharpe ratio. Default: portfolio.min_sharpe in params.nuon.
    --sortino: float  # Minimum training Sortino ratio. Default: portfolio.min_sortino in params.nuon.
    --debug  # Write debug messages to /tmp/thesis/log.txt.
]: nothing -> nothing {
    debug-mode $debug

    let book = (load-params).portfolio
    let roi_threshold = $roi | default $book.min_roi
    let sharpe_threshold = $sharpe | default $book.min_sharpe
    let sortino_threshold = $sortino | default $book.min_sortino

    let rows = (
        load-prices
        | buy-and-hold --k $k --rank $rank --roi $roi_threshold --sharpe $sharpe_threshold
            --sortino $sortino_threshold
    )

    let summary = (portfolio-summary $rows --assets $k)

    $rows
    | polars into-df
    | polars with-column (polars col week | polars cast date | polars as week)
    | save-table $BUY_AND_HOLD_PATH

    $summary | save-table $PORTFOLIO_PATH

    let metrics = $summary | metric-record

    msg --level done $"Built ($BUY_AND_HOLD_PATH) with ($rows | length) weeks"

    msg $"ROI ($metrics.roi), Sharpe ($metrics.sharpe), Sortino ($metrics.sortino)"
}

# Print the Nushell completion for the commands.
export def "main completions" []: nothing -> nothing {
    let commands = scope commands | where name starts-with "main "
    let text = (extern-text $commands)

    print $text
}

# Render the LaTeX tables from the EDA parquet files.
export def "main tables" [
    source: path = $FILES_DIR  # Folder with the EDA parquet tables.
    output: path = $TABLES_DIR  # Folder for the LaTeX files.
]: nothing -> nothing {
    let source_text = $source | into string
    let output_text = $output | into string

    python scripts/nb/tables.py --source $source_text --output $output_text
}

# Render the SVG charts from the cleaned prices and the market series.
export def "main charts" [
    source: path = $PRICES_PATH  # Cleaned weekly prices.
    --market: path = $MARKET_PATH  # Market series from `eda`.
    --output: path = $IMAGES_DIR  # Folder for the SVG files.
]: nothing -> nothing {
    let source_text = $source | into string
    let market_text = $market | into string
    let output_text = $output | into string

    python scripts/nb/charts.py --source $source_text --market $market_text --output $output_text
}

# Fit the CatBoost model and write the conformal predictions. This is a skeleton.
export def "main model fit" []: nothing -> nothing {
    let dataset_text = $DATASET_PATH | into string
    let output_text = $PREDICTIONS_PATH | into string

    python scripts/nb/model.py --dataset $dataset_text --output $output_text
}
