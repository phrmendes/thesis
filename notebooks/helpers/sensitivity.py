import polars as pl
from helpers.market import market_series
from helpers.params import load_params
from helpers.portfolio import selected_roi
from helpers.sales import sale_regression


def sensitivity_row(
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
    params = load_params()["portfolio"]
    thresholds = {"roi": params["min_roi"], "sharpe": params["min_sharpe"], "sortino": params["min_sortino"]}
    market = market_series(prices)
    terms = sale_regression(market, shift_days)
    first_half = terms.filter(pl.col("term") == "fh").row(0, named=True)
    post_sale = terms.filter(pl.col("term") == "post").row(0, named=True)
    market_geometric_return = market.select(pl.col("market_log_return").mean().exp() - 1).item()

    return pl.DataFrame(
        {
            "variant": [label],
            "items": [prices["name"].n_unique()],
            "market_geometric_return": [market_geometric_return],
            "fh_coefficient": [first_half["equal_coefficient"]],
            "fh_p_value": [first_half["equal_p_value"]],
            "post_coefficient": [post_sale["equal_coefficient"]],
            "post_p_value": [post_sale["equal_p_value"]],
            "portfolio_roi": [selected_roi(prices, size, thresholds, window)],
        }
    )
