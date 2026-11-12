from functools import cache
from pathlib import Path
from tomllib import load
from typing import TypedDict, cast

PARAMS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "params.toml"


class CollectionParams(TypedDict):
    """The collection window of the daily snapshots."""

    first_date: str
    last_date: str


class CleanParams(TypedDict):
    """The cleaning thresholds and the return cap."""

    return_cap: float
    training_share: float
    min_price_multiple: float
    max_price_multiple: float
    min_mean_price: float
    min_observations: int
    min_day_share: float
    max_gap_days: int
    max_unchanged_days: int


class EdaParams(TypedDict):
    """The EDA thresholds."""

    item_min_days: int
    regime_break: str
    turn_of_year_start: str
    turn_of_year_end: str
    sale_lag_days: int


class EvalParams(TypedDict):
    """The walk-forward evaluation windows."""

    initial_days: int
    step_days: int
    horizon_days: int


class ChartEvent(TypedDict):
    """One dated event that the market chart marks."""

    name: str
    date: str


class ChartParams(TypedDict):
    """The chart settings and the events to mark."""

    volatility_days: int
    bin_width: float
    raw_ceiling: float
    events: list[ChartEvent]


class PortfolioParams(TypedDict):
    """The portfolio fee and the minimum training ratios."""

    net_sale_share: float
    min_roi: float
    min_sharpe: float
    min_sortino: float
    max_stale_days: int
    price_window_days: int
    random_draws: int
    seed: int
    k_sweep: list[int]


class SalePeriod(TypedDict):
    """One Steam sale period with its season."""

    season: str
    start: str
    end: str


class SensitivityVariant(TypedDict):
    """The name of one sensitivity variant. The other keys override one cleaning choice."""

    name: str


class SensitivityParams(TypedDict):
    """The variants of the sensitivity run."""

    variants: list[SensitivityVariant]


class Parameters(TypedDict):
    """The sections of the parameter file."""

    collection: CollectionParams
    clean: CleanParams
    eda: EdaParams
    eval: EvalParams
    charts: ChartParams
    portfolio: PortfolioParams
    sale_periods: list[SalePeriod]
    sensitivity: SensitivityParams


@cache
def load_params() -> Parameters:
    """Read the tunable methodology values that Nushell also reads.

    Returns:
        The values as typed sections.

    """
    with PARAMS_PATH.open("rb") as handle:
        return cast("Parameters", load(handle))
