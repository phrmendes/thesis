-- This query creates cleaned.prices from raw.prices. It selects assets with a
-- mean csgotrader price of at least 1 and at least 500 positive observations.
-- It calculates weekly closing prices.
-- It carries the last observed quote forward.

CREATE SCHEMA IF NOT EXISTS cleaned;

CREATE OR REPLACE TABLE cleaned.prices AS
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

weekly_horizon AS (
    SELECT DISTINCT date_trunc('week', date) AS week_start
    FROM raw.prices
    WHERE prices['csgotrader'] > 0
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
            FROM selected_assets
            WHERE selected_assets.id = raw_prices.id
        )
    GROUP BY raw_prices.id, date_trunc('week', raw_prices.date)
),

asset_week_grid AS (
    SELECT
        selected_assets.id,
        selected_assets.name,
        selected_assets.family,
        selected_assets.rarity,
        weekly_horizon.week_start,
        (
            SELECT observed_weekly_prices.observed_price
            FROM observed_weekly_prices
            WHERE
                observed_weekly_prices.id = selected_assets.id
                AND (
                    observed_weekly_prices.week_start
                    = weekly_horizon.week_start
                )
        ) AS observed_price
    FROM selected_assets
    CROSS JOIN weekly_horizon
),

forward_filled_prices AS (
    SELECT
        id,
        name,
        family,
        rarity,
        week_start,
        last_value(observed_price IGNORE NULLS) OVER (
            PARTITION BY id
            ORDER BY week_start
        ) AS price
    FROM asset_week_grid
)

SELECT
    week_start,
    id,
    name,
    family,
    rarity,
    price
FROM forward_filled_prices
WHERE price IS NOT NULL;

ALTER TABLE cleaned.prices RENAME COLUMN week_start TO week;
