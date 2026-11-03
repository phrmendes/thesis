const DEFAULT_LOG_FILE = "/tmp/thesis/log.txt"
const BAR_WIDTH = 30

# Return whether the output uses color and symbols.
def color-enabled []: nothing -> bool {
    if not (is-terminal --stderr) { return false }

    ($env.NO_COLOR? == null)
}

# Format one line without color or symbol.
def format-plain [level: string, text: string]: nothing -> string {
    if $level == "warn" { return $"warning: ($text)" }

    $text
}

# Format one line. `plain` leaves out the color and the symbol.
export def format-line [
    level: string
    text: string
    --plain
    --color
]: nothing -> string {
    if $plain { return (format-plain $level $text) }

    if (not $color) and (not (color-enabled)) { return (format-plain $level $text) }

    match $level {
        done => $"(ansi green)✓(ansi reset) ($text)"
        warn => $"(ansi yellow)!(ansi reset) ($text)"
        debug => $"(ansi dark_gray)· ($text)(ansi reset)"
        _ => $"(ansi cyan)•(ansi reset) ($text)"
    }
}

# Append one message to the debug log as a JSON line. Do nothing when debug is off.
export def debug-line [text: string]: nothing -> nothing {
    if ($env.THESIS_DEBUG? | default "false") != "true" { return }

    let path = $env.THESIS_LOG_FILE? | default $DEFAULT_LOG_FILE

    mkdir (($path | path parse).parent)

    let line = (
        {
            time: (date now | format date "%Y-%m-%dT%H:%M:%S%.3f%z")
            level: "debug"
            message: $text
        }
        | to json --raw
    )

    $"($line)\n" | save --append $path
}

# Print one human-readable message on stderr.
export def msg [text: string, --level: string = "info"]: nothing -> nothing {
    if $level == "debug" {
        debug-line $text

        return
    }

    print --stderr (format-line $level $text)
}

# Turn the debug log on or off for the current command. An enabled run starts with an empty log file and prints its path.
export def --env debug-mode [enabled: bool]: nothing -> nothing {
    $env.THESIS_DEBUG = ($enabled | into string)

    if not $enabled { return }

    let path = $env.THESIS_LOG_FILE? | default $DEFAULT_LOG_FILE

    mkdir (($path | path parse).parent)

    "" | save --force $path

    msg $"Debug log: ($path)"
}

# Return one progress bar without the numbers.
export def bar-text [done: int, total: int]: nothing -> string {
    if $total <= 0 { return ("" | fill --width $BAR_WIDTH --character "█") }

    let ratio = ([
        ($done / $total)
        1
    ] | math min)

    let filled = $ratio * $BAR_WIDTH | math floor | into int
    let empty = ($BAR_WIDTH - $filled)

    ("" | fill --width $filled --character "█") + ("" | fill --width $empty --character "░")
}

# Draw the progress of a long step. Redraw one line on a terminal and print one line per tenth otherwise.
export def progress [done: int, total: int, --label: string = ""]: nothing -> nothing {
    let line = $"[($done)/($total)] ($label)"

    if not (is-terminal --stderr) {
        if $done == 0 { msg $line }

        return
    }

    let ratio = (if $total > 0 { $done / $total } else { 1 })
    let percent = ($ratio * 100 | math round | into int)
    let suffix = (if $done >= $total { "\n" } else { "" })

    print --stderr --no-newline $"\r[($done)/($total)] (bar-text $done $total) ($percent)% ($label)($suffix)"
}

# Run one action and print its duration. The action receives the pipeline input.
export def timed [
    label: string
    action: closure
    --step: int
    --of: int
]: any -> any {
    let start = (date now)
    let result = (do $action $in)
    let elapsed = ((date now) - $start)
    let seconds = $elapsed / 1sec | math round --precision 1
    let counter = (if $step == null or $of == null { "" } else { $"[($step)/($of)] " })

    msg --level done $"($counter)($label) ($seconds)s"

    debug-line $"($label): ($elapsed)"

    $result
}
