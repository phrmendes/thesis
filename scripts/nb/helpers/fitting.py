import sys
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from pathlib import Path


class ModelNotDefinedError(NotImplementedError):
    """Raise when the model features and target are not defined yet."""


def fit(dataset: pl.DataFrame) -> pl.DataFrame:
    """Fit the model and return one prediction row per observation.

    The features, the target, and the time split are not defined yet. CatBoost
    will fit the quantile regressors and MAPIE the conformal intervals.

    Raises:
        ModelNotDefinedError: The model features and target are not defined yet.

    """
    print(f"the model is not defined yet ({dataset.height} rows)", file=sys.stderr)
    raise ModelNotDefinedError


def write_predictions(dataset_file: Path, output_file: Path) -> pl.DataFrame:
    """Fit the model on the dataset and write the predictions.

    Returns:
        The predictions.

    """
    predictions = fit(pl.read_parquet(dataset_file))
    output_file.parent.mkdir(parents=True, exist_ok=True)
    predictions.write_parquet(output_file)
    print(f"Written {output_file}")
    return predictions
