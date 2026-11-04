import polars as pl
from statsmodels.tsa.stattools import acf, adfuller


def ratio(numerator: pl.Expr, denominator: pl.Expr) -> pl.Expr:
    """Divide two expressions, or return null when the denominator is not positive.

    Returns:
        The ratio expression.

    """
    return pl.when(denominator > 0).then(numerator / denominator)


def autocorrelations(values: list[float], max_lag: int) -> list[float]:
    """Calculate the autocorrelation of a series at each lag from one to the maximum.

    Returns:
        The autocorrelation of each lag.

    """
    return list(acf(values, nlags=max_lag)[1:])


def adf_test(values: list[float]) -> tuple[float, float]:
    """Run an augmented Dickey-Fuller test.

    Returns:
        The test statistic and its p-value.

    """
    statistic, p_value, *_ = adfuller(values, autolag="AIC")

    return float(statistic), float(p_value)


def column_min(column: str) -> pl.Expr:
    """Take the minimum of a float column.

    The Polars `min` kernel returns a wrong value for float columns of 16 rows or more in this environment.
    The lowest quantile returns the true minimum.

    Returns:
        The expression for the minimum.

    """
    return pl.col(column).quantile(0.0, interpolation="lower").alias(column)


def column_max(column: str) -> pl.Expr:
    """Take the maximum of a float column. See `column_min`.

    Returns:
        The expression for the maximum.

    """
    return pl.col(column).quantile(1.0, interpolation="higher").alias(column)
