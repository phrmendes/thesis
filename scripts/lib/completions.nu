# Add the parameter comment when the signature has a description.
def add-note [prefix: string, parameter: record]: nothing -> string {
    if ($parameter.description? | describe) != "string" { return $prefix }

    if (($parameter.description | str trim) | is-empty) { return $prefix }

    $"($prefix)  # ($parameter.description)"
}

# Format one parameter of an extern signature.
def build-signature-line [parameter: record]: nothing -> string {
    let shape = $parameter.syntax_shape? | default "string"
    let optional = if ($parameter.is_optional? | default false) { "?" } else { "" }

    if $parameter.parameter_type == "switch" {
        return (add-note $"    --($parameter.parameter_name)" $parameter)
    }

    if $parameter.parameter_type == "named" {
        return (add-note $"    --($parameter.parameter_name): ($shape)" $parameter)
    }

    add-note $"    ($parameter.parameter_name)($optional): ($shape)" $parameter
}

# Return the indented comment line above one command, or an empty string.
def build-description-line [command: record]: nothing -> string {
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
export def build-extern-text [commands: table]: nothing -> string {
    let blocks = (
        $commands
        | sort-by name
        | each {|command|
            let name = $command.name | str replace "main " "thesis "

            let parameters = (
                $command.signatures
                | values
                | flatten
                | where parameter_type in ["named" "switch" "positional"]
            )

            let lines = $parameters | each {|parameter| build-signature-line $parameter } | str join "\n"
            let head = (build-description-line $command)
            $"($head)  export extern \"($name)\" [\n($lines)\n  ]"
        }
    )

    let body = $blocks | str join "\n\n"

    $"module completions {\n($body)\n}\n\nexport use completions *\n"
}
