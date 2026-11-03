use std/assert

use ../lib/output.nu [bar-text debug-line debug-mode format-line msg timed]

# A plain line has no color and no symbol. A warning keeps its level.
assert equal (format-line info "hello" --plain) "hello"
assert equal (format-line warn "careful" --plain) "warning: careful"
assert equal (format-line done "ready" --plain) "ready"

# A colored line has an escape and the symbol of its level.
assert ((format-line info "hello" --color) =~ "•")
assert ((format-line done "ready" --color) =~ "✓")
assert ((format-line warn "careful" --color) =~ "!")
assert ((format-line info "hello" --color) =~ "\\e\\[36m")

# A raw debug message writes nothing when debug is off.
let dir = (mktemp --directory)
let path = ($dir | path join "log.txt")
with-env {THESIS_LOG_FILE: $path} {
    debug-line "hidden"

    assert (not ($path | path exists))
}

# With debug on, each message is one JSON line with a time, a level and a message.
with-env {THESIS_DEBUG: "true", THESIS_LOG_FILE: $path} {
    debug-line "first"

    debug-line "second"
}

let lines = (open $path | lines)
assert equal ($lines | length) 2
let first = ($lines | first | from json)
assert equal $first.level "debug"
assert equal $first.message "first"
assert (($first.time | describe) == "string")

# An enabled run starts with an empty log file. A disabled run writes nothing more.
with-env {THESIS_LOG_FILE: $path} {
    debug-mode true

    debug-line "only this line"

    debug-mode false

    debug-line "hidden"
}

let written = (open $path | lines)
assert equal ($written | length) 1
assert equal ($written | first | from json | get message) "only this line"

# The bar is empty at zero, half at half, and full at the total.
let width = (bar-text 10 10 | split chars | length)
assert equal (bar-text 0 10 | str replace --all "░" "" | split chars | length) 0
assert equal (bar-text 5 10 | str replace --all "░" "" | split chars | length) 15
assert equal (bar-text 10 10 | str replace --all "█" "" | split chars | length) 0
assert equal (bar-text 0 0 | split chars | length) $width

# The timer returns the action result and passes the pipeline input.
assert equal (7 | timed "test" {|value| $value * 2 }) 14

# A message reaches stderr, not stdout.
let script = ($dir | path join "message.nu")
[
    $"use ($env.FILE_PWD)/../lib/output.nu [msg]"
    "msg 'to stderr'"
] | str join "\n" | save $script
let printed = (nu $script | complete)
assert equal ($printed.stdout | str trim) ""
assert (($printed.stderr | str trim) == "to stderr")
rm --recursive --force $dir
