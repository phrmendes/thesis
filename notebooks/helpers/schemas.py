from typing import TYPE_CHECKING, Literal

import polars as pl

if TYPE_CHECKING:
    from pathlib import Path

PERIODS = ("training", "validation", "testing")

SELECTION_REASONS = ("selected", "low_price", "few_observations", "no_training_data")

TableName = Literal["prices", "assets", "audit", "portfolio", "portfolio_universe"]

SCHEMAS: dict[TableName, pl.Schema] = {
    "portfolio": pl.Schema(
        {
            "assets": pl.Int32(),
            "days": pl.UInt32(),
            "sale_fee": pl.Float64(),
            "roi": pl.Float64(),
            "sharpe": pl.Float64(),
            "sortino": pl.Float64(),
        }
    ),
    "portfolio_universe": pl.Schema({"name": pl.String()}),
    "prices": pl.Schema(
        {
            "name": pl.String(),
            "rarity": pl.Categorical(),
            "date": pl.Date(),
            "period": pl.Enum(PERIODS),
            "price": pl.Float64(),
            "return": pl.Float64(),
            "raw_return": pl.Float64(),
            "price_7d": pl.Float64(),
            "composite_price": pl.Float64(),
            "buff_price": pl.Float64(),
        }
    ),
    "assets": pl.Schema(
        {
            "name": pl.String(),
            "first_date": pl.Date(),
            "last_date": pl.Date(),
            "positive_days": pl.UInt64(),
            "training_mean_price": pl.Float64(),
            "training_observations": pl.UInt64(),
            "reason": pl.Enum(SELECTION_REASONS),
        }
    ),
    "audit": pl.Schema(
        {
            "name": pl.String(),
            "date": pl.Date(),
            "price": pl.Float64(),
            "positive": pl.Boolean(),
            "usable": pl.Boolean(),
            "selected": pl.Boolean(),
            "valid": pl.Boolean(),
        }
    ),
}


def read_table(name: TableName, path: Path) -> pl.DataFrame:
    """Read one Parquet input with its declared schema.

    Polars cannot build an enum or a category while it reads a Parquet file, so one cast applies the schema.
    The cast also raises an error when a closed set receives an unknown value.

    Returns:
        The table with every column in its declared type.

    """
    return pl.read_parquet(path).cast(SCHEMAS[name])
