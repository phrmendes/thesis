-- This query creates portfolios.buy_and_hold from raw.prices and
-- cleaned.returns. It selects assets from runtime strategy parameters.
-- It gives equal initial weights and applies a 10% fee at final sale.

CREATE OR REPLACE MACRO sale_net_factor() AS (0.9);
CREATE OR REPLACE MACRO return_cap() AS (1.0);

CREATE SCHEMA IF NOT EXISTS portfolios;

CREATE TEMP TABLE buy_and_hold_weekly_prices AS
WITH ordered_weeks AS (
    SELECT
        weekly_horizon.week AS week_start,
        row_number() OVER (ORDER BY weekly_horizon.week) AS week_number,
        count(*) OVER () AS total_weeks
    FROM (
        SELECT DISTINCT week
        FROM cleaned.returns
    ) AS weekly_horizon
),

week_periods AS (
    SELECT
        week_start,
        CASE
            WHEN week_number <= floor(total_weeks * 2.0 / 3) THEN 'training'
            ELSE 'testing'
        END AS period
    FROM ordered_weeks
),

candidate_assets AS (
    SELECT DISTINCT
        id,
        name,
        family,
        rarity
    FROM cleaned.returns
),

observed_weekly_prices AS (
    SELECT
        raw_prices.id,
        date_trunc('week', raw_prices.date) AS week_start,
        arg_max(
            raw_prices.prices['csgotrader'],
            raw_prices.date
        ) AS observed_price
    FROM raw.prices AS raw_prices
    WHERE
        raw_prices.prices['csgotrader'] > 0
        AND EXISTS (
            SELECT 1
            FROM candidate_assets
            WHERE candidate_assets.id = raw_prices.id
        )
    GROUP BY raw_prices.id, date_trunc('week', raw_prices.date)
),

asset_week_grid AS (
    SELECT
        candidate_assets.id,
        week_periods.week_start,
        week_periods.period,
        (
            SELECT observed_weekly_prices.observed_price
            FROM observed_weekly_prices
            WHERE
                observed_weekly_prices.id = candidate_assets.id
                AND observed_weekly_prices.week_start = week_periods.week_start
        ) AS observed_price
    FROM candidate_assets
    CROSS JOIN week_periods
),

forward_filled_prices AS (
    SELECT
        id,
        week_start,
        period,
        last_value(observed_price IGNORE NULLS) OVER (
            PARTITION BY id
            ORDER BY week_start
        ) AS closing_price
    FROM asset_week_grid
)

SELECT
    id,
    week_start,
    period,
    closing_price
FROM forward_filled_prices
WHERE closing_price IS NOT NULL;

CREATE TEMP TABLE buy_and_hold_selected_assets AS
WITH weekly_asset_returns AS (
    SELECT
        id,
        week_start,
        period,
        closing_price,
        closing_price / lag(closing_price) OVER (
            PARTITION BY id
            ORDER BY week_start
        ) - 1 AS gross_return
    FROM buy_and_hold_weekly_prices
),

training_price_series AS (
    SELECT
        id,
        week_start,
        closing_price,
        least(
            greatest(gross_return, -return_cap()), return_cap()
        ) AS capped_return
    FROM weekly_asset_returns
    WHERE period = 'training'
),

training_metrics AS (
    SELECT
        id,
        week_start,
        first_value(closing_price) OVER (
            PARTITION BY id
            ORDER BY week_start
        ) AS initial_price,
        last_value(closing_price) OVER (
            PARTITION BY id
            ORDER BY week_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS final_price,
        avg(capped_return) OVER (PARTITION BY id) AS average_return,
        stddev(capped_return) OVER (PARTITION BY id) AS return_stddev,
        avg(
            CASE
                WHEN capped_return < 0 THEN capped_return * capped_return
                ELSE 0
            END
        ) OVER (PARTITION BY id) AS return_semivariance,
        row_number() OVER (
            PARTITION BY id
            ORDER BY week_start DESC
        ) AS final_training_week
    FROM training_price_series
),

candidate_metrics AS (
    SELECT
        id,
        sale_net_factor() * final_price / initial_price - 1 AS roi,
        average_return / nullif(return_stddev, 0) AS sharpe,
        average_return / nullif(sqrt(return_semivariance), 0) AS sortino
    FROM training_metrics
    WHERE
        final_training_week = 1
        AND return_stddev IS NOT NULL
),

eligible_candidates AS (
    SELECT
        candidate_metrics.id,
        candidate_metrics.roi,
        candidate_metrics.sharpe,
        candidate_metrics.sortino,
        (
            candidate_metrics.roi >= strategy_parameters.roi
            AND candidate_metrics.sharpe >= strategy_parameters.sharpe
            AND candidate_metrics.sortino >= strategy_parameters.sortino
        ) AS is_eligible
    FROM candidate_metrics
    CROSS JOIN strategy_parameters
)

SELECT
    ranked_candidates.id,
    ranked_candidates.roi,
    ranked_candidates.sharpe,
    ranked_candidates.sortino
FROM (
    SELECT
        id,
        roi,
        sharpe,
        sortino,
        is_eligible,
        CASE
            WHEN is_eligible THEN row_number() OVER (
                PARTITION BY is_eligible
                ORDER BY roi DESC
            )
        END AS roi_rank
    FROM eligible_candidates
) AS ranked_candidates
WHERE
    ranked_candidates.is_eligible
    AND ranked_candidates.roi_rank <= (
        SELECT strategy_parameters.portfolio_size
        FROM strategy_parameters
    );

CREATE OR REPLACE TABLE portfolios.buy_and_hold AS
WITH test_positions AS (
    SELECT
        test_prices.id,
        test_prices.week_start,
        test_prices.closing_price,
        first_value(test_prices.closing_price) OVER (
            PARTITION BY test_prices.id
            ORDER BY test_prices.week_start
        ) AS initial_price
    FROM buy_and_hold_selected_assets
    CROSS JOIN buy_and_hold_weekly_prices AS test_prices
    WHERE
        buy_and_hold_selected_assets.id = test_prices.id
        AND test_prices.period = 'testing'
),

portfolio_values AS (
    SELECT
        week_start,
        sum(
            closing_price / initial_price
            / (
                SELECT strategy_parameters.portfolio_size
                FROM strategy_parameters
            )
        ) AS portfolio_value
    FROM test_positions
    GROUP BY week_start
),

portfolio_return_base AS (
    SELECT
        week_start,
        portfolio_value,
        lag(portfolio_value) OVER (ORDER BY week_start) AS previous_value,
        row_number() OVER (ORDER BY week_start DESC) AS final_week
    FROM portfolio_values
),

capped_returns AS (
    SELECT
        week_start,
        portfolio_value,
        CASE
            WHEN previous_value IS NULL THEN NULL
            WHEN final_week = 1
                THEN least(
                    greatest(
                        sale_net_factor() * portfolio_value
                        / previous_value - 1,
                        -return_cap()
                    ),
                    return_cap()
                )
            ELSE least(
                greatest(portfolio_value / previous_value - 1, -return_cap()),
                return_cap()
            )
        END AS return_value
    FROM portfolio_return_base
),

portfolio_metrics AS (
    SELECT
        week_start,
        portfolio_value,
        return_value,
        first_value(portfolio_value) OVER (
            ORDER BY week_start
        ) AS initial_value,
        last_value(portfolio_value) OVER (
            ORDER BY week_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS final_gross_value,
        avg(return_value) OVER () AS average_return,
        stddev(return_value) OVER () AS return_stddev,
        avg(
            CASE
                WHEN return_value < 0 THEN return_value * return_value
                ELSE 0
            END
        ) OVER () AS return_semivariance
    FROM capped_returns
)

SELECT
    week_start,
    portfolio_value,
    return_value,
    sale_net_factor() * final_gross_value / initial_value - 1 AS roi,
    average_return / nullif(return_stddev, 0) AS sharpe,
    average_return / nullif(sqrt(return_semivariance), 0) AS sortino
FROM portfolio_metrics;

ALTER TABLE portfolios.buy_and_hold RENAME COLUMN week_start TO week;
ALTER TABLE portfolios.buy_and_hold RENAME COLUMN return_value TO return;
ALTER TABLE portfolios.buy_and_hold RENAME COLUMN portfolio_value TO value;
