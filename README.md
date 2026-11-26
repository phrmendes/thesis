# :mortar_board: Thesis

My economics bachelor's thesis (UFABC)!

# Dependencies

- [Nushell](https://www.nushell.sh) with the polars plugin
- [Python](https://www.python.org) 3.14 or newer
- [TeX Live](https://www.tug.org/texlive/)
- [Pandoc](https://pandoc.org/)

The optional [devenv](https://devenv.sh/) environment provides these tools. `uv` installs the locked Python wheels.

# Usage

Nushell fetches and cleans the data. Python runs the notebooks and the portfolio, and writes the tables and the charts.

```bash
thesis data fetch
thesis data clean
thesis eda
thesis portfolio buy-and-hold
thesis sensitivity
thesis render
```

Run `buy-and-hold` before `sensitivity`, because sensitivity reads the selected portfolio size. Run `thesis --help` to list the commands. Without devenv, use `nu scripts/thesis.nu` instead of `thesis`.

# Layout

| Path                                                   | Content                                                    |
| ------------------------------------------------------ | ---------------------------------------------------------- |
| `scripts/`                                             | Nushell commands and modules                               |
| `notebooks/`                                           | Python notebooks and helpers                               |
| `parameters.toml`                                      | Shared paths, cleaning settings, and sensitivity variants  |
| `scripts/parameters.toml`, `notebooks/parameters.toml` | Settings of each language                                  |
| `files/`                                               | Data (gitignored)                                          |
| `output/`                                              | Charts, LaTeX tables, executed notebooks, and `thesis.pdf` |

Open the notebooks with `open-nb`.

# Rendered notebooks

| Notebook         | File                                             |
| ---------------- | ------------------------------------------------ |
| Data quality     | [ipynb](output/notebooks/data_quality.ipynb)     |
| Returns          | [ipynb](output/notebooks/returns.ipynb)          |
| Market           | [ipynb](output/notebooks/market.ipynb)           |
| Calendar effects | [ipynb](output/notebooks/calendar_effects.ipynb) |
| Evaluation       | [ipynb](output/notebooks/evaluation.ipynb)       |
| Portfolio        | [ipynb](output/notebooks/portfolios.ipynb)       |
| Sensitivity      | [ipynb](output/notebooks/sensitivity.ipynb)      |
