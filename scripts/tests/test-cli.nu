use std/assert

const ROOT = (path self | path dirname | path dirname | path dirname)
const CLI = ($ROOT | path join "scripts" "thesis.nu")

# Run the pipeline commands end to end in a temporary directory. The commands use relative paths, so the working directory keeps the real files/ folder untouched.
let origin = $env.PWD
let work = (mktemp --directory)

# Build 800 days of prices for three assets. The price rises with a repeating wobble, so the weekly returns have both signs and a nonzero spread.
let days = (1..800 | each {|index| (2021-01-04 | into datetime) + ($index * 1day) })

let assets = [
    {
        name: "Alpha | Test (Factory New)"
        rarity: "Covert"
    }

    {
        name: "Beta | Test (Minimal Wear)"
        rarity: "Classified"
    }

    {
        name: "Gamma | Test (Field-Tested)"
        rarity: "Mil-Spec"
    }
]

let raw_rows = (
    $assets | each {|asset|
        $days | enumerate | each {|row|
            let base = (10.0 + ($row.index * 0.01))
            let wobble = ((($row.index * 7) mod 23) - 11)
            let price = (($base * (100 + $wobble)) / 100)

            {
                date: $row.item
                name: $asset.name
                price: $price
                steam_24h: $price
                composite_price: ($price * 1.01)
                buff_price: ($price * 0.9)
            }
        }
    } | flatten
)

mkdir ($work | path join "files/raw")

$raw_rows
| polars into-df
| polars with-column (polars col date | polars cast date | polars as date)
| polars save ($work | path join "files/raw/2021-01-04.parquet")

$assets
| reduce --fold {} {|asset, acc|
    let entry = {
        market_hash_name: $asset.name
        rarity: {name: $asset.rarity}
    }

    $acc | merge {($asset.name): $entry}
}
| to json
| save --force ($work | path join "files/items.json")

# Run the commands as the user does, from the temporary directory.
cd $work

for args in [
    [data clean]
    [eda]
    [portfolio buy-and-hold --k 1 --rank sharpe]
] {
    let result = (nu $CLI ...$args | complete)

    assert equal $result.exit_code 0
}

# The audit and the portfolio use the shared metric schema.
let audit = (polars open "files/audit.parquet" --eager)

assert equal ($audit | polars columns | first 2) [metric_name metric_value]

let summary = (polars open "files/portfolio.parquet" --eager)

assert equal ($summary | polars columns | first 2) [metric_name metric_value]
let is_assets = ((polars col metric_name) == "assets")
let assets = ($summary | polars filter $is_assets | polars into-nu | first | get metric_value)

assert equal $assets "1"

# Every expected file exists.
for name in [audit prices assets coverage_daily returns portfolio buy_and_hold] {
    assert equal ($"files/($name).parquet" | path exists) true
}

# `--help` lists every command.
let help = (nu $CLI --help | complete)

assert equal $help.exit_code 0

let commands = [
    "data fetch"
    "data clean"
    "eda"
    "portfolio buy-and-hold"
    "tables"
    "charts"
]

for name in $commands {
    let listed = ($help.stdout | lines | any {|line| ($line | str trim) | str starts-with $"thesis.nu ($name)" })

    assert $listed $"help does not list ($name)"
}

cd $origin

rm --recursive --force $work
