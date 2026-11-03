use std/assert

use ../lib/completions.nu [extern-text]
use ../thesis.nu *

const ROOT = (path self | path dirname | path dirname | path dirname)

# The declarations come from the signatures: a named flag, a switch and an optional positional.
let signatures = {
    first: [
        {
            parameter_name: "start"
            parameter_type: "named"
            syntax_shape: "string"
            is_optional: false
            description: "Start day."
        }
        {
            parameter_name: "force"
            parameter_type: "switch"
            syntax_shape: null
            is_optional: false
            description: "Run again."
        }
        {
            parameter_name: "source"
            parameter_type: "positional"
            syntax_shape: "path"
            is_optional: true
            description: ""
        }
    ]
}
let commands = [[name signatures description]; ["main sample run" $signatures "Sample command."]]
let text = (extern-text $commands)

assert ($text =~ "export use completions \\*")
assert ($text =~ 'export extern "thesis sample run" \[')
assert ($text =~ '    --start: string  # Start day.')
assert ($text =~ '    --force  # Run again.')
assert ($text =~ 'source\?: path')
assert ($text =~ '  # Sample command.\n  export extern "thesis sample run"')

# A command without a description gives no comment line.
let bare = (extern-text [[name signatures]; ["main bare" $signatures]])
assert (not ($bare =~ "(?m)^\\s*# "))
# The name loses the `main` prefix. An empty table gives one empty line.
let renamed = (extern-text [[name signatures]; ["main eda" $signatures]])

assert ($renamed =~ 'extern "thesis eda"')
assert (not ((extern-text []) =~ "export extern "))
assert ((extern-text []) =~ "export use completions")

# The real command prints declarations that Nushell parses. The count must match the number of CLI commands, so a new command needs no edit here.
let work = (mktemp --directory)
let generated = ($work | path join "completions.nu")
let script = ($ROOT | path join "scripts" "thesis.nu")
let printed = (nu $script completions | complete)

assert equal $printed.exit_code 0
$printed.stdout | save --force $generated

let counter = ($work | path join "count.nu")
[
    $"use ($generated) *"
    "scope externs | where name starts-with 'thesis' | length"
] | str join "\n" | save $counter
let check = (nu $counter | complete)
let expected = (scope commands | where name starts-with "main " | length)

assert equal $check.exit_code 0
assert equal ($check.stdout | str trim | into int) $expected

# Every declaration has a description above it, so the completion list shows it.
let blocks = ($printed.stdout | str trim | split row "\n\n")
let undescribed = ($blocks | where ($it | str starts-with "extern "))

assert equal ($undescribed | length) 0
rm --recursive --force $work
