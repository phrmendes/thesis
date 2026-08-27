-- This query builds cleaned.prices from raw.prices. The inputs are the
-- csgotrader price data and the SteamDB sale calendar. The output is
-- cleaned.prices, which the model and portfolio commands consume. The main rule
-- keeps weekly closing prices, drops spurious prices and the first week of each
-- asset, and labels each week with its sale season or none.

CREATE SCHEMA IF NOT EXISTS cleaned;

CREATE OR REPLACE MACRO sale_net_factor() AS (0.9);
CREATE OR REPLACE MACRO return_cap() AS (1.0);
CREATE OR REPLACE MACRO price_floor_factor() AS (0.05);
CREATE OR REPLACE MACRO price_ceiling_factor() AS (20.0);

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

asset_reference_prices AS (
    SELECT
        asset_prices.id,
        median(asset_prices.csgotrader) AS reference_price
    FROM (
        SELECT
            raw_prices.id,
            raw_prices.prices['csgotrader'] AS csgotrader
        FROM raw.prices AS raw_prices
        WHERE
            raw_prices.prices['csgotrader'] > 0
            AND EXISTS (
                SELECT 1
                FROM selected_assets
                WHERE selected_assets.id = raw_prices.id
            )
    ) AS asset_prices
    GROUP BY asset_prices.id
),

weekly_horizon AS (
    SELECT DISTINCT date_trunc('week', date) AS week_start
    FROM raw.prices
    WHERE prices['csgotrader'] > 0
),

observed_weekly_closing AS (
    SELECT
        raw_prices.id,
        date_trunc('week', raw_prices.date) AS week_start,
        arg_max(
            raw_prices.prices['csgotrader'], raw_prices.date
        ) AS weekly_close
    FROM raw.prices AS raw_prices
    INNER JOIN asset_reference_prices AS reference
        ON raw_prices.id = reference.id
    WHERE
        raw_prices.prices['csgotrader'] > 0
        AND raw_prices.prices['csgotrader']
        >= price_floor_factor() * reference.reference_price
        AND raw_prices.prices['csgotrader']
        <= price_ceiling_factor() * reference.reference_price
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
            SELECT observed_weekly_closing.weekly_close
            FROM observed_weekly_closing
            WHERE
                observed_weekly_closing.id = selected_assets.id
                AND observed_weekly_closing.week_start
                = weekly_horizon.week_start
        ) AS weekly_close
    FROM selected_assets
    CROSS JOIN weekly_horizon
),

forward_filled_weekly AS (
    SELECT
        id,
        name,
        family,
        rarity,
        week_start,
        last_value(weekly_close IGNORE NULLS) OVER (
            PARTITION BY id
            ORDER BY week_start
        ) AS price
    FROM asset_week_grid
),

weekly_series AS (
    SELECT
        id,
        name,
        family,
        rarity,
        week_start,
        price,
        price / lag(price) OVER (
            PARTITION BY id
            ORDER BY week_start
        ) AS price_ratio,
        price / lag(price) OVER (
            PARTITION BY id
            ORDER BY week_start
        ) - 1 AS raw_return
    FROM forward_filled_weekly
    WHERE price IS NOT NULL
),

asset_daily_prices AS (
    SELECT
        raw_prices.id,
        raw_prices.date,
        date_trunc('week', raw_prices.date) AS week_start,
        raw_prices.prices['csgotrader'] AS csgotrader
    FROM raw.prices AS raw_prices
    INNER JOIN asset_reference_prices AS reference
        ON raw_prices.id = reference.id
    WHERE
        raw_prices.prices['csgotrader'] > 0
        AND raw_prices.prices['csgotrader']
        >= price_floor_factor() * reference.reference_price
        AND raw_prices.prices['csgotrader']
        <= price_ceiling_factor() * reference.reference_price
        AND EXISTS (
            SELECT 1
            FROM selected_assets
            WHERE selected_assets.id = raw_prices.id
        )
),

within_week_daily AS (
    SELECT
        id,
        week_start,
        csgotrader / lag(csgotrader) OVER (
            PARTITION BY id, week_start
            ORDER BY date
        ) - 1 AS daily_return,
        first_value(csgotrader) OVER (
            PARTITION BY id, week_start
            ORDER BY date
        ) AS first_close,
        last_value(csgotrader) OVER (
            PARTITION BY id, week_start
            ORDER BY date
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS last_close
    FROM asset_daily_prices
),

within_week_stats AS (
    SELECT
        id,
        week_start,
        last_close / first_close - 1 AS week_return,
        stddev(daily_return) AS week_daily_std,
        sqrt(
            avg(
                CASE
                    WHEN daily_return < 0 THEN daily_return * daily_return
                    ELSE 0
                END
            )
        ) AS week_daily_downside
    FROM within_week_daily
    GROUP BY id, week_start, first_close, last_close
),

sale_periods AS (
    SELECT
        'autumn' AS season,
        DATE '2020-11-25' AS start_date,
        DATE '2020-12-01' AS end_date
    UNION ALL
    SELECT
        'winter' AS season,
        DATE '2020-12-22' AS start_date,
        DATE '2021-01-05' AS end_date
    UNION ALL
    SELECT
        'summer' AS season,
        DATE '2021-06-24' AS start_date,
        DATE '2021-07-08' AS end_date
    UNION ALL
    SELECT
        'autumn' AS season,
        DATE '2021-11-24' AS start_date,
        DATE '2021-12-01' AS end_date
    UNION ALL
    SELECT
        'winter' AS season,
        DATE '2021-12-22' AS start_date,
        DATE '2022-01-05' AS end_date
    UNION ALL
    SELECT
        'summer' AS season,
        DATE '2022-06-23' AS start_date,
        DATE '2022-07-07' AS end_date
    UNION ALL
    SELECT
        'autumn' AS season,
        DATE '2022-11-22' AS start_date,
        DATE '2022-11-29' AS end_date
    UNION ALL
    SELECT
        'winter' AS season,
        DATE '2022-12-22' AS start_date,
        DATE '2023-01-05' AS end_date
    UNION ALL
    SELECT
        'spring' AS season,
        DATE '2023-03-16' AS start_date,
        DATE '2023-03-23' AS end_date
    UNION ALL
    SELECT
        'summer' AS season,
        DATE '2023-06-29' AS start_date,
        DATE '2023-07-13' AS end_date
),

week_sale_season AS (
    SELECT
        weekly_horizon.week_start,
        coalesce(
            min(sale_periods.season),
            'none'
        ) AS sale_season
    FROM weekly_horizon
    LEFT JOIN sale_periods
        ON NOT (
            weekly_horizon.week_start > sale_periods.end_date
            OR weekly_horizon.week_start + INTERVAL '6 days'
            < sale_periods.start_date
        )
    GROUP BY weekly_horizon.week_start
)

SELECT
    weekly_series.id,
    weekly_series.name,
    weekly_series.family,
    weekly_series.rarity,
    weekly_series.week_start,
    weekly_series.price,
    least(
        greatest(weekly_series.raw_return, -return_cap()), return_cap()
    ) AS return_value,
    sale_net_factor() * weekly_series.price_ratio - 1 AS roi,
    within_week_stats.week_return
    / nullif(within_week_stats.week_daily_std, 0) AS sharpe,
    within_week_stats.week_return
    / nullif(within_week_stats.week_daily_downside, 0) AS sortino,
    week_sale_season.sale_season
FROM weekly_series
LEFT JOIN within_week_stats
    ON
        weekly_series.id = within_week_stats.id
        AND weekly_series.week_start = within_week_stats.week_start
LEFT JOIN week_sale_season
    ON weekly_series.week_start = week_sale_season.week_start
WHERE weekly_series.raw_return IS NOT NULL;

ALTER TABLE cleaned.prices RENAME COLUMN week_start TO week;
ALTER TABLE cleaned.prices RENAME COLUMN return_value TO return;
