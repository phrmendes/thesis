# :mortar_board: Thesis

My economics bachelor's thesis (UFABC)!

# Dependencies

- [Nushell](https://www.nushell.sh) with the polars plugin
- [Python](https://www.python.org) 3.14 or newer
- [TeX Live](https://www.tug.org/texlive/)
- [Pandoc](https://pandoc.org/)

`devenv` provides every tool and every Python package.

# Data pipeline

Nushell builds the data. Python renders the tables and the charts.

`scripts/thesis.nu` holds the commands. `scripts/params.nuon` holds the tunable methodology values. `scripts/lib/` holds the pipeline modules, `scripts/nb/` the marimo notebooks and their helpers, and `scripts/tests/` the tests.

The main price is the Steam 7-day sales average from the daily csgotrader.app snapshots.

```bash
thesis data fetch
thesis data clean
thesis eda
thesis portfolio buy-and-hold --k 10
thesis tables
thesis charts
```

Run `thesis --help` to list the commands and their flags. The `thesis` command comes from `devenv.nix`, so run it inside `devenv shell`. Nushell completions are generated from the command signatures before the shell starts.

The pipeline writes the data to `files/`, the LaTeX tables to `tex/tables/`, and the charts to `images/` as PDF, because `lualatex` cannot read an SVG. `files/` is gitignored.

Open a notebook with `marimo edit scripts/nb/tables.py`. It reads the same flags as the command, so it runs without arguments.
