from pathlib import Path
from typing import Self, cast

import polars as pl
from duckdb import connect

from .constants import DEFAULT_DB_PATH, SQL_DIR


class StrategyValidationError(ValueError):
    """Raise when a buy-and-hold request is invalid."""

    @classmethod
    def insufficient_eligible_assets(cls, portfolio_size: int, available: int) -> Self:
        return cls(f"requested K value ({portfolio_size}) exceeds eligible asset count ({available})")


def buy_and_hold(
    portfolio_size: int,
    roi: float,
    sharpe: float,
    sortino: float,
    db_path: Path | None = None,
) -> int:
    """Build a buy-and-hold strategy for one portfolio size."""
    db_path = db_path or Path(DEFAULT_DB_PATH)
    strategy_query = (SQL_DIR / "buy_and_hold.sql").read_text()
    validation_query = (SQL_DIR / "validate_portfolio_sizes.sql").read_text()
    count_query = (SQL_DIR / "count_buy_and_hold_rows.sql").read_text()

    with connect(str(db_path)) as conn:
        conn.register(
            "strategy_parameters",
            pl.DataFrame(
                {
                    "portfolio_size": [portfolio_size],
                    "roi": [roi],
                    "sharpe": [sharpe],
                    "sortino": [sortino],
                }
            ),
        )
        conn.begin()
        conn.execute(strategy_query)
        invalid_sizes = conn.sql(validation_query).pl()

        if invalid_sizes.height:
            conn.rollback()
            available = cast(int, invalid_sizes["selected_assets"].item())
            raise StrategyValidationError.insufficient_eligible_assets(portfolio_size, available)

        conn.commit()

    with connect(str(db_path), read_only=True) as conn:
        return cast(int, conn.sql(count_query).pl().item())
