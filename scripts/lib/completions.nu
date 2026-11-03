# Add the parameter comment when the signature has a description.
def with-note [prefix: string, param: record]: nothing -> string {
    if ($param.description? | describe) != "string" { return $prefix }

    if (($param.description | str trim) | is-empty) { return $prefix }

    $"($prefix)  # ($param.description)"
}

# Format one parameter of an extern signature.
def signature-line [param: record]: nothing -> string {
    let shape = $param.syntax_shape? | default "string"
    let optional = if ($param.is_optional? | default false) { "?" } else { "" }

    if $param.parameter_type == "switch" {
        return (with-note $"    --($param.parameter_name)" $param)
    }

    if $param.parameter_type == "named" {
        return (with-note $"    --($param.parameter_name): ($shape)" $param)
    }

    with-note $"    ($param.parameter_name)($optional): ($shape)" $param
}

# Return the indented comment line above one command, or an empty string.
def description-line [command: record]: nothing -> string {
    if ($command.description? | describe) != "string" { return "" }

    let note = (
        $command.description
        | lines
        | first
        | str trim
    )

    if ($note | is-empty) { return "" }

    $"  # ($note)\n"
}

# Turn the command signatures into Nushell extern declarations.
export def extern-text [commands: table]: nothing -> string {
    let blocks = (
        $commands
        | sort-by name
        | each {|command|
            let name = $command.name | str replace "main " "thesis "

            let params = (
                $command.signatures
                | values
                | flatten
                | where parameter_type in ["named" "switch" "positional"]
            )

            let lines = $params | each {|param| signature-line $param } | str join "\n"
            let head = (description-line $command)
            $"($head)  export extern \"($name)\" [\n($lines)\n  ]"
        }
    )

    let body = $blocks | str join "\n\n"

    $"module completions {\n($body)\n}\n\nexport use completions *\n"
}
