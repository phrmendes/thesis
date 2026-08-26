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
