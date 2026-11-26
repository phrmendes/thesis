import polars as pl
from helpers.market import get_market_series
from helpers.parameters import parameters
from helpers.portfolio import calculate_selected_roi
from helpers.sales import fit_sale_regression


def build_sensitivity_row(
    prices: pl.DataFrame,
    label: str,
    size: int,
    shift_days: int = 0,
    window: int | None = None,
) -> pl.DataFrame:
    """Summarize the key results of one variant: the sample, the market return, the sale phases, and the portfolio.

    Returns:
        One row with the items, the market compound return, the first-half and post-sale coefficients, and the ROI.

    """
    portfolio_parameters = parameters().portfolios
    thresholds = {
        "roi": portfolio_parameters.min_roi,
        "sharpe": portfolio_parameters.min_sharpe,
        "sortino": portfolio_parameters.min_sortino,
    }
    market = get_market_series(prices)
    terms = fit_sale_regression(market, shift_days)
    first_half = terms.filter(pl.col("term") == "fh").row(0, named=True)
    post_sale = terms.filter(pl.col("term") == "post").row(0, named=True)
    geometric_return = market.select(pl.col("log_return").mean().exp() - 1).item()

    return pl.DataFrame(
        {
            "variant": [label],
            "items": [prices["name"].n_unique()],
            "geometric_return": [geometric_return],
            "fh_coefficient": [first_half["equal_coefficient"]],
            "fh_p_value": [first_half["equal_p_value"]],
            "post_coefficient": [post_sale["equal_coefficient"]],
            "post_p_value": [post_sale["equal_p_value"]],
            "portfolio_roi": [calculate_selected_roi(prices, size, thresholds, window)],
        },
        schema_overrides={"portfolio_roi": pl.Float64},
    )
