use std/assert

use ../lib/fetch.nu [
    classify-response
    flatten-snapshot
    is-cached
    items-rarity
    snapshot-files
    snapshot-path
    summarize-statuses
]

# Redirects and HTML pages are gaps. Server errors fail.
assert equal (classify-response 301 "") gap
assert equal (classify-response 200 "<html></html>") gap
assert equal (classify-response 500 "{}") failed
assert equal (classify-response 200 '{"A": {}}') ok

# A cache file must exist and hold data.
let path = (mktemp --suffix .parquet)

assert equal (is-cached $path) false

"data" | save --force $path

assert equal (is-cached $path) true

rm --force $path

# The flatten keeps the Steam 7-day price as the main price, reads the Steam 24-hour, composite and BUFF prices, stores a missing price as 0.0, and drops an empty name.
let body = '{"A": {"steam": {"last_7d": 9.0, "last_24h": 8.5}, "csgotrader": {"price": 12.5}, "buff163": {"starting_at": {"price": 8.0}}}, "B": {"steam": {"last_7d": null}}, "C": {"buff163": {"starting_at": "null"}}, "": {"csgotrader": {"price": 3.0}}}'
let prices = (flatten-snapshot $body "2021-01-04" | polars collect | polars into-nu)

assert equal ($prices | length) 3
assert equal ($prices | where name == "A" | first | get price) 9.0
assert equal ($prices | where name == "A" | first | get steam_24h) 8.5
assert equal ($prices | where name == "A" | first | get composite_price) 12.5
assert equal ($prices | where name == "A" | first | get buff_price) 8.0
assert equal ($prices | where name == "B" | first | get price) 0.0
assert equal ($prices | where name == "C" | first | get steam_24h) 0.0
assert equal ($prices | where name == "C" | first | get buff_price) 0.0

# A snapshot path and the snapshot glob use the raw folder.
assert equal (snapshot-path "2021-01-04" "/tmp/data" | into string) "/tmp/data/2021-01-04.parquet"

let dir = (mktemp --directory)

"" | save --force ($dir | path join "2021-01-04.parquet")

"" | save --force ($dir | path join "2021-01-05.parquet")

assert equal (snapshot-files $dir | length) 2

rm --recursive $dir

# The fetch summary counts the records and lists the failed days.
let summary = (
    summarize-statuses [
        {day: "2021-01-04", status: "fetched"}
        {day: "2021-01-05", status: "failed"}
        {day: "2021-01-06", status: "cached"}
        {day: "2021-01-08", status: "gap"}
        {day: "2021-01-07", status: "gap"}
    ]
)

assert equal $summary.fetched 1
assert equal $summary.skipped 3
assert equal $summary.failed 1
assert equal $summary.failures ["2021-01-05"]
assert equal $summary.gaps ["2021-01-07" "2021-01-08"]

# The item metadata keeps each name and its rarity, including a missing rarity.
let items_path = (mktemp --suffix .json)

'{"a": {"market_hash_name": "A", "rarity": {"name": "rare"}}, "b": {"market_hash_name": "B"}}' | save --force $items_path

let items = (items-rarity $items_path | polars collect | polars into-nu)

assert equal ($items | where name == "A" | first | get rarity) "rare"
assert equal ($items | where name == "B" | first | get rarity) null

rm --force $items_path
