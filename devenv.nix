{
  pkgs,
  inputs,
  config,
  ...
}:

let
  at = inputs.academic-templates.packages.${pkgs.stdenv.hostPlatform.system}.academic-templates;
  python = pkgs.python314.withPackages (
    ps: with ps; [
      altair
      catboost
      great-tables
      marimo
      polars
      scikit-learn
      statsmodels
      vl-convert-python
      (ps.callPackage ./mapie.nix { })
    ]
  );
in
{
  name = "thesis";

  env.XDG_DATA_DIRS = "${config.devenv.state}/share";

  languages = {
    texlive = {
      enable = true;
      base = pkgs.texliveSmall.withPackages (ps: [ at ]);
    };
    python = {
      enable = true;
      lsp.package = pkgs.pyrefly;
      package = python;
    };
  };

  packages = with pkgs; [
    (nushell.withPlugins (with nushellPlugins; [ polars ]))
    duckdb
    gfortran
    graphviz
    gzip
    liberation_ttf
    nu-lint
    pandoc
    pyrefly
    zlib
  ];

  scripts.thesis = {
    description = "Run the thesis pipeline. Use `thesis --help`.";
    exec = ''exec nu "$DEVENV_ROOT/scripts/thesis.nu" "$@"'';
  };

  tasks = {
    "thesis:build".exec = "pandoc --defaults pandoc.yaml thesis.md";
    "thesis:lint".exec = "nu-lint scripts -c nu-lint.toml";
    "thesis:test".exec = "nu scripts/tests/test.nu";
    "thesis:completions" = {
      exec = ''
        mkdir -p "$DEVENV_STATE/share/nushell/vendor/autoload"
        thesis completions > "$DEVENV_STATE/share/nushell/vendor/autoload/thesis.nu" || true
      '';
      before = [ "devenv:enterShell" ];
    };
  };

  treefmt.config.programs = {
    texfmt.enable = true;
  };

  git-hooks.hooks = {
    ripsecrets.enable = true;
    ruff.enable = true;
    ruff-format.enable = true;
    pyrefly = {
      enable = true;
      name = "pyrefly";
      entry = "pyrefly check";
      language = "system";
      types = [ "python" ];
      pass_filenames = false;
    };
    nushell = {
      enable = true;
      name = "nushell";
      entry = "nu-lint scripts -c nu-lint.toml";
      language = "system";
      files = "\\.nu$";
      pass_filenames = false;
    };
  };
}
