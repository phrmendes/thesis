use ../lib/helpers.nu [fail]
use ../lib/output.nu [msg]

let files = (glob $"($env.FILE_PWD)/test-*.nu")
let total = ($files | length)

mut failed = 0

for row in ($files | enumerate) {
    let name = ($row.item | path basename)
    let result = (nu $row.item | complete)

    if $result.exit_code != 0 {
        msg --level warn $"($row.index + 1)/($total) ($name)"

        msg --level warn $result.stdout

        msg --level warn $result.stderr

        $failed += 1
    } else {
        msg --level done $"($row.index + 1)/($total) ($name)"
    }
}

if $failed > 0 {
    fail $"($failed) of ($total) test files failed" $failed --label "test failures"
}

msg --level done $"All ($total) test files passed"
