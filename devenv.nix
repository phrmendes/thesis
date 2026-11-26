{
  pkgs,
  inputs,
  config,
  ...
}:

let
  at = inputs.academic-templates.packages.${pkgs.stdenv.hostPlatform.system}.academic-templates;
in
{
  name = "thesis";

  env.XDG_DATA_DIRS = "${config.devenv.state}/share";
  env.IPYTHONDIR = "${config.devenv.root}/ipython";

  languages = {
    texlive = {
      enable = true;
      base = pkgs.texliveSmall.withPackages (ps: [ at ]);
    };
    python = {
      enable = true;
      package = pkgs.python314;
      lsp.package = pkgs.pyrefly;
      manylinux.enable = true;
      venv.enable = true;
      uv = {
        enable = true;
        sync = {
          enable = true;
          arguments = [ "--frozen" ];
        };
      };
    };
  };

  packages = with pkgs; [
    (nushell.withPlugins (with nushellPlugins; [ polars ]))
    gfortran
    graphviz
    gzip
    nu-lint
    pandoc
    pyrefly
    zlib
  ];

  scripts = {
    thesis = {
      description = "Thesis CLI";
      exec = ''exec nu "$DEVENV_ROOT/scripts/thesis.nu" "$@"'';
    };
    open-nb = {
      description = "Open the notebooks in JupyterLab";
      exec = ''exec jupyter lab --notebook-dir="$DEVENV_ROOT/notebooks" --ServerApp.browser="''${BROWSER:-chromium}" "$@"'';
    };
  };

  tasks = {
    "thesis:build".exec = "pandoc --defaults pandoc.yaml thesis.md";
    "thesis:lint".exec = "nu-lint scripts -c nu-lint.toml";
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
