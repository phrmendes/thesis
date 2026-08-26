-- This query checks that the selected asset count equals the requested K value.
-- The buy-and-hold command uses this result before it commits the portfolio.

SELECT
    strategy_parameters.portfolio_size,
    (
        SELECT count(*)
        FROM buy_and_hold_selected_assets
    ) AS selected_assets
FROM strategy_parameters
WHERE
    (
        SELECT count(*)
        FROM buy_and_hold_selected_assets
    ) <> strategy_parameters.portfolio_size
