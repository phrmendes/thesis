# :mortar_board: Thesis

My economics bachelor's thesis (UFABC)!

# Dependencies

- [Nushell](https://www.nushell.sh) with the polars plugin
- [Python](https://www.python.org) 3.14 or newer
- [TeX Live](https://www.tug.org/texlive/)
- [Pandoc](https://pandoc.org/)

`devenv` provides every tool and every Python package.

# Data pipeline

Nushell fetches and cleans the data. Python audits the cleaning, runs the EDA and the portfolio, and renders the tables and the charts.

`scripts/thesis.nu` holds the commands. `scripts/params.toml` holds the tunable methodology values. `scripts/lib/` holds the Nushell modules, `notebooks/` the Python notebooks, their helpers and their tests, and `scripts/tests/` the Nushell tests.

The main price is the Steam 7-day sales average from the daily csgotrader.app snapshots.

```bash
thesis data fetch
thesis data clean
thesis eda
thesis portfolio buy-and-hold --k 10
```

Run `thesis --help` to list the commands and their flags. The `thesis` command comes from `devenv.nix`, so run it inside `devenv shell`. Nushell completions are generated from the command signatures before the shell starts.

The pipeline writes the data to `files/`, the LaTeX tables to `tex/tables/`, and the charts to `images/` as PNG. `files/` is gitignored.

Open the notebooks with `devenv tasks run thesis:nb`. The task serves `notebooks` in JupyterLab, where a `.py` file opens as a notebook. Each notebook reads the same flags as its command, so it runs without arguments.
