-- This query creates cleaned.returns from raw.prices. It selects assets with a
-- mean csgotrader price of at least 1 and at least 500 positive observations.
-- It calculates capped weekly closing-price returns and risk-adjusted metrics.

CREATE OR REPLACE MACRO return_cap() AS (1.0);

CREATE SCHEMA IF NOT EXISTS cleaned;

CREATE OR REPLACE TABLE cleaned.returns AS
WITH selected_assets AS (
    SELECT
        id,
        name,
        family,
        rarity
    FROM raw.prices
    GROUP BY id, name, family, rarity
    HAVING
        avg(prices['csgotrader']) FILTER (WHERE prices['csgotrader'] > 0) >= 1.0
        AND count(*) FILTER (WHERE prices['csgotrader'] > 0) >= 500
),

daily_prices AS (
    SELECT
        raw_prices.id,
        raw_prices.name,
        raw_prices.family,
        raw_prices.rarity,
        raw_prices.date,
        raw_prices.prices['csgotrader'] AS price
    FROM raw.prices AS raw_prices
    WHERE
        raw_prices.prices['csgotrader'] > 0
        AND EXISTS (
            SELECT 1
            FROM selected_assets
            WHERE selected_assets.id = raw_prices.id
        )
),

weekly_prices AS (
    SELECT
        id,
        name,
        family,
        rarity,
        date_trunc('week', date) AS week_start,
        arg_max(price, date) AS closing_price
    FROM daily_prices
    GROUP BY id, name, family, rarity, date_trunc('week', date)
),

weekly_returns AS (
    SELECT
        id,
        name,
        family,
        rarity,
        week_start,
        closing_price / lag(closing_price) OVER (
            PARTITION BY id
            ORDER BY week_start
        ) - 1 AS return_value
    FROM weekly_prices
),

valid_returns AS (
    SELECT
        id,
        name,
        family,
        rarity,
        week_start,
        return_value
    FROM weekly_returns
    WHERE return_value IS NOT NULL
),

winsorized AS (
    SELECT
        id,
        name,
        family,
        rarity,
        week_start,
        least(
            greatest(return_value, -return_cap()), return_cap()
        ) AS return_value
    FROM valid_returns
),

with_ratios AS (
    SELECT
        id,
        name,
        family,
        rarity,
        week_start,
        return_value,
        avg(return_value) OVER (PARTITION BY id) AS average_return,
        stddev(return_value) OVER (PARTITION BY id) AS return_stddev,
        avg(
            CASE
                WHEN return_value < 0 THEN return_value * return_value
                ELSE 0
            END
        ) OVER (PARTITION BY id) AS return_semivariance
    FROM winsorized
)

SELECT
    week_start,
    id,
    name,
    family,
    rarity,
    return_value,
    average_return / nullif(return_stddev, 0) AS sharpe,
    average_return / nullif(sqrt(return_semivariance), 0) AS sortino
FROM with_ratios;

ALTER TABLE cleaned.returns RENAME COLUMN week_start TO week;
ALTER TABLE cleaned.returns RENAME COLUMN return_value TO return;
