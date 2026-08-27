from pathlib import Path
from typing import Annotated

from typer import Exit, Option, Typer, secho

from .buy_and_hold import PortfolioValidationError, buy_and_hold
from .constants import DEFAULT_DB_PATH, DEFAULT_ROI, DEFAULT_SHARPE, DEFAULT_SORTINO

app = Typer(name="portfolio", help="Portfolio construction")


@app.command(name="buy-and-hold", help="Build a one-unit buy-and-hold portfolio")
def buy_and_hold_cmd(
    portfolio_size: Annotated[int, Option("--k", min=1)],
    roi: Annotated[float, Option("--roi")] = DEFAULT_ROI,
    sharpe: Annotated[float, Option("--sharpe")] = DEFAULT_SHARPE,
    sortino: Annotated[float, Option("--sortino")] = DEFAULT_SORTINO,
    db_path: Annotated[str, Option("--db-path")] = DEFAULT_DB_PATH,
) -> None:
    try:
        rows = buy_and_hold(portfolio_size, roi, sharpe, sortino, Path(db_path))
    except PortfolioValidationError as error:
        secho(str(error), fg="red")
        raise Exit(1) from None

    secho(f"Built {rows:,} buy-and-hold portfolio weeks", fg="green")
