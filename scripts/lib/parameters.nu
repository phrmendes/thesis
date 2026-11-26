export const GLOBAL_PARAMETERS_PATH = (
    path self
    | path dirname
    | path dirname
    | path dirname
    | path join "parameters.toml"
)

export const PARAMETERS_PATH = (
    path self
    | path dirname
    | path dirname
    | path join "parameters.toml"
)

# Return the shared and Nushell settings as one record.
export def load-parameters []: nothing -> record {
    open $GLOBAL_PARAMETERS_PATH | merge (open $PARAMETERS_PATH)
}
