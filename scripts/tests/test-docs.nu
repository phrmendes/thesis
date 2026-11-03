use std/assert

use ../thesis.nu *

# Every argument of every CLI command has a description. The help output and the editor read the same signature.
let commands = [
    "main data fetch"
    "main data clean"
    "main eda"
    "main portfolio buy-and-hold"
    "main tables"
    "main charts"
    "main model fit"
]

for name in $commands {
    let command = (scope commands | where name == $name | first)

    let params = (
        $command.signatures
        | values
        | first
        | where parameter_type in ["named" "switch" "positional"]
    )
    for param in $params {
        let described = (($param.description? | describe) == "string")

        assert ($described and (($param.description | str trim | is-not-empty))) $"($name) has an undocumented argument ($param.parameter_name)"
    }
}
