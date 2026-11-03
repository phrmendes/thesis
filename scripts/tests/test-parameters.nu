use std/assert

use ../lib/helpers.nu [fail parse-price sale-season with-retry]

use ../lib/output.nu [timed]

# Prices accept numbers and numeric strings. Missing and bad values are null.
assert equal ("123.5" | parse-price) 123.5
assert equal (7 | parse-price) 7.0
assert equal (null | parse-price) null
assert equal ("null" | parse-price) null
assert equal ("abc" | parse-price) null

# The retry returns the first success and raises after the last attempt.
assert equal (with-retry 2 { 7 }) 7

# The retry waits one second and succeeds on the next attempt.
let start = (date now)
let retried = (with-retry 2 {
    if ((date now) - $start) < 1sec {
        fail "not yet" 1 --label "retry"
    }

    7
})

assert equal $retried 7

let failed = (try {
    with-retry 1 {
        fail "the retry test fails on purpose" 1 --label "retry"
    }

    false
} catch { true })

assert $failed

# The sale season follows the sale periods.
assert equal (sale-season (2021-06-28 | into datetime)) summer
assert equal (sale-season (2021-03-01 | into datetime)) none

# The timer returns the action result.
assert equal (timed "test" {|| 7 }) 7
