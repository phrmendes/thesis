from typing import TYPE_CHECKING

import polars as pl
from helpers.sales import PHASES
from numpy import eye

if TYPE_CHECKING:
    from statsmodels.regression.linear_model import RegressionResultsWrapper


def run_joint_phase_test(model: RegressionResultsWrapper) -> tuple[float, float]:
    """Test that the four phase coefficients are all zero, with a Wald test on the Newey-West covariance.

    The phase terms follow the constant. The turn-of-the-year term comes last and stays out of the test.

    Returns:
        The Wald statistic and its p-value.

    """
    result = model.wald_test(eye(len(model.params))[1 : len(PHASES)], scalar=True)

    return float(result.statistic), float(result.pvalue)


def tabulate_joint_tests(models: dict[str, RegressionResultsWrapper]) -> pl.DataFrame:
    """Run the joint test of the phase coefficients.

    Returns:
        One row per model.

    """
    rows = []

    for label, model in models.items():
        statistic, p_value = run_joint_phase_test(model)
        rows.append({"model": label, "statistic": statistic, "p_value": p_value})

    return pl.DataFrame(rows)
