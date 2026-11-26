from math import floor

import polars as pl
from statsmodels.tsa.stattools import acf


def calculate_hac_lags(observations: int) -> int:
    """Choose the Newey-West bandwidth with the rule reported by Wooldridge, section 12.5.

    Returns:
        The bandwidth `floor(4 * (observations / 100) ** (2 / 9))`.

    """
    return floor(4 * (observations / 100) ** (2 / 9))


def calculate_ratio(numerator: pl.Expr, denominator: pl.Expr) -> pl.Expr:
    """Divide two expressions, or return null when the denominator is not positive.

    Returns:
        The ratio expression.

    """
    return pl.when(denominator > 0).then(numerator / denominator)


def calculate_autocorrelations(values: list[float], max_lag: int) -> list[float]:
    """Calculate the autocorrelation of a series at each lag from one to the maximum.

    Returns:
        The autocorrelation of each lag.

    """
    return list(acf(values, nlags=max_lag)[1:])


def get_column_min(column: str) -> pl.Expr:
    """Take the minimum of a float column.

    The Polars `min` kernel returns a wrong value for float columns of 16 rows or more in this environment.
    The lowest quantile returns the true minimum.

    Returns:
        The expression for the minimum.

    """
    return pl.col(column).quantile(0.0, interpolation="lower").alias(column)


def get_column_max(column: str) -> pl.Expr:
    """Take the maximum of a float column. See `column_min`.

    Returns:
        The expression for the maximum.

    """
    return pl.col(column).quantile(1.0, interpolation="higher").alias(column)
