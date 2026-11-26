from functools import cache
from pathlib import Path
from tomllib import load
from typing import Annotated, Literal

from msgspec import UNSET, Meta, Struct, UnsetType, convert

GLOBAL_PARAMETERS_PATH = Path(__file__).resolve().parents[2] / "parameters.toml"
PARAMETERS_PATH = Path(__file__).resolve().parents[1] / "parameters.toml"


class PathParameters(Struct, forbid_unknown_fields=True):
    """The shared data and analysis output paths."""

    prices: str
    assets: str
    audit: str
    buy_and_hold: str
    portfolio: str
    portfolio_universe: str
    sensitivity: str
    tables: str
    images: str


class CleanParameters(Struct, forbid_unknown_fields=True):
    """The cleaning thresholds and the return cap."""

    return_cap: float
    training_share: Annotated[float, Meta(gt=0, lt=1)]
    validation_share: Annotated[float, Meta(gt=0, lt=1)]
    min_price_multiple: float
    max_price_multiple: float
    min_mean_price: float
    min_observations: int
    min_day_share: float
    max_gap_days: int
    max_unchanged_days: int


class ChartEvent(Struct, forbid_unknown_fields=True):
    """One dated event in a chart."""

    name: str
    date: str


class SalePeriod(Struct, forbid_unknown_fields=True):
    """One Steam sale period."""

    season: str
    start: str
    end: str


class SensitivityVariant(Struct, forbid_unknown_fields=True):
    """One named cleaning variant with a display label and optional overrides."""

    name: str
    label: str
    min_observations: int | UnsetType = UNSET
    min_day_share: float | UnsetType = UNSET
    max_gap_days: int | UnsetType = UNSET
    return_cap: float | UnsetType = UNSET


class HelperParameters(Struct, forbid_unknown_fields=True):
    """The shared rendering, file, and sampling settings."""

    locale: str
    font_family: str
    date_format: str
    table_source: str
    heading_align: Literal["left", "center", "right"]
    title_anchor: Literal["start", "middle", "end"]
    title_align: Literal["left", "center", "right"]
    legend_orient: Literal["left", "right", "top", "bottom"]
    chart_width: int
    chart_height: int
    png_scale: float
    item_min_days: int
    expensive_price: int


class DataQualityParameters(Struct, forbid_unknown_fields=True):
    """The data quality settings."""

    top_jump_days: int
    cheap_price: float
    up_jump: float
    down_jump: float
    reversal_range: list[float]
    day_bucket_breaks: list[int]
    day_bucket_labels: list[str]
    share_bucket_breaks: list[float]
    share_bucket_labels: list[str]


class ReturnParameters(Struct, forbid_unknown_fields=True):
    """The returns settings."""

    bin_width: float
    raw_ceiling: float
    top_assets: int
    large_return: float
    grid_points: int
    grid_padding: float
    grid_percentiles: list[int]
    price_bucket_breaks: list[int]
    price_bucket_labels: list[str]
    density_width: int
    density_height: int
    density_columns: int
    density_opacity: float


class MarketParameters(Struct, forbid_unknown_fields=True):
    """The market settings."""

    lags: list[int]
    volatility_days: int
    index_height: int
    volatility_height: int
    line_styles: list[list[int]]
    events: list[ChartEvent]


class CalendarParameters(Struct, forbid_unknown_fields=True):
    """The calendar effects settings."""

    min_segment_items: int
    sensitivity_lags: list[int]
    turn_of_year_start: str
    turn_of_year_end: str
    sale_lag_days: int
    sale_periods: list[SalePeriod]


class EvaluationParameters(Struct, forbid_unknown_fields=True):
    """The evaluation settings."""

    regime_break: str


class PortfolioParameters(Struct, forbid_unknown_fields=True):
    """The portfolios settings."""

    roi_tolerance: Annotated[float, Meta(ge=0)]
    rank: Literal["roi", "sharpe", "sortino"]
    net_sale_share: float
    min_roi: float
    min_sharpe: float
    min_sortino: float
    max_stale_days: int
    price_window_days: int
    random_draws: int
    seed: int
    k_sweep: list[int]


class SensitivityParameters(Struct, forbid_unknown_fields=True):
    """The sensitivity settings."""

    sale_shifts: list[int]
    price_window_days: int


class Parameters(Struct, forbid_unknown_fields=True):
    """The shared and Python notebook settings."""

    paths: PathParameters
    clean: CleanParameters
    sensitivity_variants: list[SensitivityVariant]
    helpers: HelperParameters
    data_quality: DataQualityParameters
    returns: ReturnParameters
    market: MarketParameters
    calendar_effects: CalendarParameters
    evaluation: EvaluationParameters
    portfolios: PortfolioParameters
    sensitivity: SensitivityParameters


@cache
def parameters() -> Parameters:
    """Read and validate shared and Python notebook settings.

    Returns:
        The shared settings and one typed section per notebook and helper group.

    Raises:
        ValueError: The files repeat a section or contain invalid settings.

    """
    with GLOBAL_PARAMETERS_PATH.open("rb") as handle:
        shared = load(handle)

    with PARAMETERS_PATH.open("rb") as handle:
        notebook = load(handle)

    duplicates = shared.keys() & notebook.keys()

    if duplicates:
        message = f"Duplicate parameter sections: {', '.join(sorted(duplicates))}"
        raise ValueError(message)

    parameters = convert(shared | notebook, type=Parameters, strict=True)

    if parameters.clean.training_share + parameters.clean.validation_share >= 1:
        message = "training_share and validation_share must leave a positive testing share"
        raise ValueError(message)

    return parameters
