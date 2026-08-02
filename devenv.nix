{
  pkgs,
  inputs,
  ...
}:

let
  academic-templates = inputs.academic-templates.packages.${pkgs.system}.academic-templates;
  tex = pkgs.texliveSmall.withPackages (ps: [ academic-templates ]);
in
{
  name = "thesis";

  languages.python = {
    enable = true;
    package = pkgs.python314;
    venv.enable = true;
    lsp.package = pkgs.basedpyright;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  packages = with pkgs; [
    pandoc
    tex
    liberation_ttf
    gfortran
    zlib
  ];

  tasks = {
    "thesis:build".exec = "pandoc --defaults pandoc.yaml thesis.md";
  };
}
