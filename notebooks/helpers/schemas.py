from typing import TYPE_CHECKING, Literal

import polars as pl
from helpers.params import load_params

if TYPE_CHECKING:
    from pathlib import Path

PERIODS = ("training", "testing")

SELECTION_REASONS = ("selected", "low_price", "few_observations", "no_training_data")

SALE_SEASONS = ["none", *dict.fromkeys(period["season"] for period in load_params()["sale_periods"])]

TableName = Literal["prices", "assets", "audit"]

SCHEMAS: dict[TableName, pl.Schema] = {
    "prices": pl.Schema(
        {
            "name": pl.String(),
            "rarity": pl.Categorical(),
            "week": pl.Date(),
            "period": pl.Enum(PERIODS),
            "price": pl.Float64(),
            "return": pl.Float64(),
            "raw_return": pl.Float64(),
            "sale_season": pl.Enum(SALE_SEASONS),
            "observed": pl.Int32(),
            "active_days": pl.Int32(),
            "composite_close": pl.Float64(),
            "buff_close": pl.Float64(),
        }
    ),
    "assets": pl.Schema(
        {
            "name": pl.String(),
            "first_week": pl.Date(),
            "last_week": pl.Date(),
            "positive_weeks": pl.UInt64(),
            "training_mean_price": pl.Float64(),
            "training_observations": pl.UInt64(),
            "reason": pl.Enum(SELECTION_REASONS),
        }
    ),
    "audit": pl.Schema(
        {
            "name": pl.String(),
            "date": pl.Date(),
            "week": pl.Date(),
            "price": pl.Float64(),
            "steam_24h": pl.Float64(),
            "positive": pl.Boolean(),
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
