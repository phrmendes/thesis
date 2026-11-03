use ./constants.nu [ITEMS_PATH RAW_DIR]
use ./helpers.nu [fail parse-price with-retry]
use ./output.nu [msg timed]

const BASE_URL = "https://prices.csgotrader.app"
const ITEMS_URL = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/{language}/all.json"
const DEFAULT_LANGUAGE = "en"

# Return the parquet path of one daily snapshot.
export def snapshot-path [day: string, dir: path]: nothing -> string {
    $dir | path join $"($day).parquet"
}

# Return the raw snapshot files of one directory.
export def snapshot-files [dir: path = $RAW_DIR]: nothing -> list<string> {
    glob ($dir | path join "*.parquet")
}

# Return whether a snapshot file holds data.
export def is-cached [path: path]: nothing -> bool {
    if not ($path | path exists) { return false }

    ((ls $path | first | get size) | into int) > 0
}

# Classify one HTTP response: ok, gap, or failed.
export def classify-response [status: int, body: string]: nothing -> string {
    if $status in [301 302 404] { return "gap" }

    if $status != 200 { return "failed" }

    if not ($body | str trim --left | str starts-with "{") { return "gap" }
    "ok"
}

# Read one optional price from an item. Return 0.0 when the path does not hold a number.
def optional-price [item: record, path: cell-path]: nothing -> float {
    try {
        $item | get --optional $path | parse-price | default 0.0
    } catch {
        0.0
    }
}

# Flatten one raw snapshot into a price table with columns date, name, price, steam_24h, composite_price, and buff_price. The price is the Steam 7-day sale average. A missing or non-numeric price is stored as 0.0 and filtered later.
export def flatten-snapshot [body: string, day: string] {
    let rows = (
        $body
        | from json
        | items {|name, item|
            {
                date: $day
                name: $name
                price: (optional-price $item steam.last_7d)
                steam_24h: (optional-price $item steam.last_24h)
                composite_price: (optional-price $item csgotrader.price)
                buff_price: (optional-price $item buff163.starting_at.price)
            }
        }
        | where not (($it.name | str trim) == "")
    )

    if ($rows | is-empty) { return null }

    msg --level debug $"flatten ($day): ($rows | length) rows"

    $rows
    | polars into-df
    | polars with-column (polars col date | polars as-date "%Y-%m-%d" | polars as date)
}

# Count the fetch results and list the failed and gap days.
export def summarize-statuses [results: list<any>]: nothing -> record {
    let fetched = $results | where status == "fetched" | length
    let failed = $results | where status == "failed" | length
    let failures = $results | where status == "failed" | get day
    let gaps = (
        $results
        | where status == "gap"
        | get day
        | sort
    )

    {
        fetched: $fetched
        skipped: (($results | length) - $fetched - $failed)
        failed: $failed
        failures: $failures
        gaps: $gaps
    }
}

# Download one daily snapshot and save it as parquet. Return its status: fetched, cached, gap, or failed.
export def fetch-day [day: string, data_dir: path, --force]: nothing -> string {
    let path = (snapshot-path $day $data_dir)

    if (not $force) and (is-cached $path) { return "cached" }

    let url = $"($BASE_URL)/($day | str replace --all '-' '/')/prices_v6.json"

    let response = (
        try { with-retry 5 { http get --full --allow-errors $url } } catch { return "failed" }
    )

    let outcome = (classify-response $response.status $response.body)

    if $outcome != "ok" { return $outcome }

    let prices = (try { flatten-snapshot $response.body $day } catch { return "failed" })

    if ($prices | describe) == "nothing" { return "gap" }

    let temporary_path = $"($path).tmp"

    $prices | polars save --type parquet $temporary_path

    mv --force $temporary_path $path

    "fetched"
}

# Download the static item metadata from the CSGO-API repository.
export def fetch-items []: nothing -> nothing {
    let url = $ITEMS_URL | str replace "{language}" $DEFAULT_LANGUAGE

    msg $"Downloading item metadata from ($url)"

    let body = (with-retry 5 { http get --raw $url })

    $body | save --force $ITEMS_PATH
}

# Load item metadata as a table with columns name and rarity.
export def items-rarity [path: path = $ITEMS_PATH] {
    if not ($path | path exists) {
        fail $"missing item metadata ($path): run 'data fetch' first" $path --label "item metadata"
    }

    let items = (
        timed "items: metadata" {||
            open $path
            | values
            | par-each {|item|
                {
                    name: ($item.market_hash_name? | default null)
                    rarity: ($item.rarity?.name?)
                }
            }
            | where name != null and name != ""
        }
    )

    if ($items | is-empty) {
        fail $"item metadata ($path) holds no item name: the file is not the CSGO-API object" $path --label "item metadata"
    }

    msg --level debug $"item metadata: ($items | length) rows"

    $items
    | polars into-df
    | polars group-by name
    | polars agg [
        (polars col rarity | polars first | polars as rarity)
    ]
}
