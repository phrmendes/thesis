# :mortar_board: Thesis

My economics bachelor's thesis (UFABC)!

# Dependencies

- [Nushell](https://www.nushell.sh) with the polars plugin
- [Python](https://www.python.org) 3.14 or newer
- [TeX Live](https://www.tug.org/texlive/)
- [Pandoc](https://pandoc.org/)

`devenv` provides every tool and every Python package.

# Data pipeline

Nushell fetches and cleans the data. Python audits the cleaning, runs the analysis notebooks and the portfolio, and renders the tables and the charts.

`scripts/thesis.nu` holds the commands. `scripts/params.toml` holds the tunable methodology values. `scripts/lib/` holds the Nushell modules, and `notebooks/` the Python notebooks and their helpers.

The main price is the Steam 24-hour sales average from the daily csgotrader.app snapshots.

```bash
thesis data fetch
thesis data clean
thesis eda
thesis portfolio buy-and-hold --k 10
thesis sensitivity
thesis render
```

`thesis eda` runs the five analysis notebooks in theme order: data quality, returns, market, calendar effects, and evaluation.

`thesis render` runs the seven notebooks and saves each one with its code and results as an `.ipynb` file in `output/notebooks/`. Run it after the pipeline.

`thesis sensitivity` rebuilds the cleaned prices for each variant in `scripts/params.toml` and writes `sensitivity.tex`. It takes a few minutes.

`thesis data clean` keeps the raw snapshots in `files/raw/`. Pass `--raw` to delete them after the cleaned tables save.

Run `thesis --help` to list the commands and their flags. The `thesis` command comes from `devenv.nix`, so run it inside `devenv shell`. Nushell completions are generated from the command signatures before the shell starts.

The pipeline writes the data to `files/`. It writes every result to `output/`: the charts as PNG in `output/images/`, the tables as LaTeX in `output/tables/`, and the executed notebooks in `output/notebooks/`. `files/` is gitignored.

Open the notebooks with `open-nb`. The script serves `notebooks` in JupyterLab, where a `.py` file opens as a notebook. Each notebook reads the same flags as its command, so it runs without arguments.

# Rendered notebooks

`thesis render` writes one executed notebook for each analysis in `output/notebooks/`. GitHub shows the text, the code, the tables, and the charts. The table cells keep their styles inline, because GitHub drops style blocks.

| Notebook | File |
| --- | --- |
| Data quality | [ipynb](output/notebooks/data_quality.ipynb) |
| Returns | [ipynb](output/notebooks/returns.ipynb) |
| Market | [ipynb](output/notebooks/market.ipynb) |
| Calendar effects | [ipynb](output/notebooks/calendar_effects.ipynb) |
| Evaluation | [ipynb](output/notebooks/evaluation.ipynb) |
| Portfolio | [ipynb](output/notebooks/portfolios.ipynb) |
| Sensitivity | [ipynb](output/notebooks/sensitivity.ipynb) |
