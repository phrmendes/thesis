from typer import Typer, secho

from .coverage import coverage
from .quality import quality
from .returns import returns

app = Typer(name="eda", help="Exploratory data analysis")


@app.command(name="coverage", help="Generate item persistence and temporal coverage tables")
def coverage_cmd() -> None:
    paths = coverage()
    for p in paths:
        secho(f"Written {p}", fg="green")


@app.command(name="returns", help="Generate weekly returns table with Sharpe and Sortino")
def returns_cmd() -> None:
    path = returns()
    secho(f"Written {path}", fg="green")


@app.command(name="quality", help="Generate cleaned-dataset quality table")
def quality_cmd() -> None:
    path = quality()
    secho(f"Written {path}", fg="green")


@app.command(name="all", help="Run all EDA commands and write every table")
def all_cmd() -> None:
    coverage_cmd()
    returns_cmd()
    quality_cmd()
