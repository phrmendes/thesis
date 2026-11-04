from functools import cache
from pathlib import Path
from tomllib import load
from typing import TypedDict, cast

PARAMS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "params.toml"


class CollectionParams(TypedDict):
    first_date: str
    last_date: str


class CleanParams(TypedDict):
    return_cap: float
    training_share: float
    min_price_multiple: float
    max_price_multiple: float
    min_mean_price: float
    min_observations: int
    max_stale_weeks: int
    max_unchanged_days: int


class EdaParams(TypedDict):
    item_min_weeks: int


class ChartEvent(TypedDict):
    name: str
    date: str


class ChartParams(TypedDict):
    volatility_weeks: int
    bin_width: float
    raw_ceiling: float
    events: list[ChartEvent]


class PortfolioParams(TypedDict):
    net_sale_share: float
    min_roi: float
    min_sharpe: float
    min_sortino: float


class SalePeriod(TypedDict):
    season: str
    start: str
    end: str


class Parameters(TypedDict):
    collection: CollectionParams
    clean: CleanParams
    eda: EdaParams
    charts: ChartParams
    portfolio: PortfolioParams
    sale_periods: list[SalePeriod]


@cache
def load_params() -> Parameters:
    """Read the tunable methodology values that Nushell also reads.

    Returns:
        The values as typed sections.

    """
    with PARAMS_PATH.open("rb") as handle:
        return cast("Parameters", load(handle))
