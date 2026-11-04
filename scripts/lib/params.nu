const PARAMS_PATH = (
    path self
    | path dirname
    | path dirname
    | path join "params.toml"
)

# Return the tunable values as one record.
export def load-params []: nothing -> record {
    open $PARAMS_PATH
}
