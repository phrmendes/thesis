-- This query checks that the selected asset count equals the requested K value.
-- The buy-and-hold command uses this result before it commits the portfolio.

SELECT
    portfolio_parameters.portfolio_size,
    (
        SELECT count(*)
        FROM buy_and_hold_selected_assets
    ) AS selected_assets
FROM portfolio_parameters
WHERE
    (
        SELECT count(*)
        FROM buy_and_hold_selected_assets
    ) <> portfolio_parameters.portfolio_size
