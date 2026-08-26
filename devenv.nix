{
  pkgs,
  inputs,
  ...
}:

let
  academic-templates =
    inputs.academic-templates.packages.${pkgs.stdenv.hostPlatform.system}.academic-templates;
in
{
  name = "thesis";

  languages = {
    texlive = {
      enable = true;
      base = pkgs.texliveSmall.withPackages (ps: [ academic-templates ]);
    };
    python = {
      enable = true;
      lsp.package = pkgs.basedpyright;
      package = pkgs.python314;
      venv.enable = true;
      uv = {
        enable = true;
        sync.enable = true;
      };
    };
  };

  packages = with pkgs; [
    pandoc
    liberation_ttf
    gfortran
    zlib
    sqlfluff
    graphviz
  ];

  tasks = {
    "thesis:build".exec = "pandoc --defaults pandoc.yaml thesis.md";
  };

  treefmt.config.programs = {
    texfmt.enable = true;
    sqlfluff.enable = true;
  };

  git-hooks.hooks = {
    ripsecrets.enable = true;
    ruff.enable = true;
    ruff-format.enable = true;
    basedpyright = {
      enable = true;
      name = "basedpyright";
      entry = "uv run basedpyright";
      language = "system";
      types = [ "python" ];
      pass_filenames = false;
    };
  };
}
