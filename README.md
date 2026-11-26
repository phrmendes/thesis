# :mortar_board: Thesis

My economics bachelor's thesis (UFABC)!

# Dependencies

- [Nushell](https://www.nushell.sh) with the polars plugin
- [Python](https://www.python.org) 3.14 or newer
- [TeX Live](https://www.tug.org/texlive/)
- [Pandoc](https://pandoc.org/)

## Optionals

- [Nix](https://nixos.org/download/) provides packages for the development environment.
- [devenv](https://devenv.sh/) configures the development environment through Nix.

The optional `devenv` environment provides the required tools and Python interpreter. `uv` installs locked Python wheels without compiling packages.

# Data pipeline

Nushell fetches and cleans the data. Python audits the cleaning, runs the analysis notebooks and the portfolio, and renders the tables and the charts.

`scripts/thesis.nu` holds the commands. `scripts/lib/` holds the Nushell modules, and `notebooks/` holds the Python notebooks and their helpers.

`parameters.toml` holds shared file paths, cleaning settings, and sensitivity variants. `scripts/parameters.toml` holds Nushell-only settings. `notebooks/parameters.toml` holds Python-only settings, with one section per notebook and a `helpers` section.

Each language reads the shared file and its own settings. Python validates the merged settings with msgspec before use.

The main price is the Steam 24-hour sales average from the daily csgotrader.app snapshots.

The default split assigns 50% of dates to training, 20% to validation, and 30% to testing. The shares apply after the first price date, which belongs to training. Asset filters and cleaning bounds use training data only.

Buy-and-hold compares portfolio sizes on validation returns, with asset rankings from training only. It maximizes daily Sharpe among portfolios within `portfolios.roi_tolerance` of the best validation ROI. The tolerance uses decimal-return units, so `0.02` means two percentage points. The final selection uses training and validation history before holding during testing.

Preliminary analyses already examined the testing period. The new procedure prevents further test-based tuning but does not erase that inspection.

`files/portfolio_universe.parquet` records the final eligible names. `files/portfolio.parquet` records the selected size in its `assets` column. The predictive strategy can reuse both artifacts for final testing. Validation eligibility must still use training history only. Sensitivity also reads that size, so run buy-and-hold before sensitivity.

```bash
thesis data fetch
thesis data clean
thesis eda
thesis portfolio buy-and-hold
thesis sensitivity
thesis render
```

`thesis eda` runs the five analysis notebooks in theme order: data quality, returns, market, calendar effects, and evaluation.

`thesis render` runs the seven notebooks and saves each one with its code and results as an `.ipynb` file in `output/notebooks/`. Run it after the pipeline.

`thesis sensitivity` rebuilds the cleaned prices for each `[[sensitivity_variants]]` entry in root `parameters.toml` and writes `sensitivity.tex`. Each variant defines a `name`, a pt-BR `label`, and its cleaning overrides. It takes a few minutes.

`thesis data clean` keeps the raw snapshots in `files/raw/`. Pass `--raw` to delete them after the cleaned tables save.

Run `thesis --help` to list the commands and their flags. Inside `devenv shell`, use `thesis`. Without devenv, replace `thesis` with `nu scripts/thesis.nu`. The development environment generates Nushell completions from the command signatures before the shell starts.

The pipeline writes the data to `files/`. It writes every result to `output/`: the charts as PNG in `output/images/`, the tables as LaTeX in `output/tables/`, and the executed notebooks in `output/notebooks/`. `files/` is gitignored.

Open the notebooks with `open-nb`. The script serves `notebooks` in JupyterLab, where a `.py` file opens as a notebook. Notebooks read all settings from the TOML files and contain no CLI parsers. The Nushell commands launch them without analysis flags.

# Rendered notebooks

`thesis render` writes one executed notebook for each analysis in `output/notebooks/`. GitHub shows the text, the code, the tables, and the charts. The table cells keep their styles inline, because GitHub drops style blocks.

| Notebook         | File                                             |
| ---------------- | ------------------------------------------------ |
| Data quality     | [ipynb](output/notebooks/data_quality.ipynb)     |
| Returns          | [ipynb](output/notebooks/returns.ipynb)          |
| Market           | [ipynb](output/notebooks/market.ipynb)           |
| Calendar effects | [ipynb](output/notebooks/calendar_effects.ipynb) |
| Evaluation       | [ipynb](output/notebooks/evaluation.ipynb)       |
| Portfolio        | [ipynb](output/notebooks/portfolios.ipynb)       |
| Sensitivity      | [ipynb](output/notebooks/sensitivity.ipynb)      |
