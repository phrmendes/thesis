CREATE OR REPLACE MACRO net_factor() AS (0.9);
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
        p.id,
        p.name,
        p.family,
        p.rarity,
        p.date,
        p.prices['csgotrader'] AS price
    FROM raw.prices AS p
    WHERE
        p.prices['csgotrader'] > 0
        AND EXISTS (
            SELECT 1
            FROM selected_assets AS u
            WHERE u.id = p.id
        )
),

weekly_prices AS (
    SELECT
        id,
        name,
        family,
        rarity,
        date_trunc('week', date) AS week_start,
        avg(price) AS mean_price,
        median(price) AS median_price
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
        mean_price,
        median_price,
        net_factor() * mean_price / lag(mean_price) OVER (
            PARTITION BY id
            ORDER BY week_start
        ) - 1 AS mean_basis_return,
        net_factor() * median_price / lag(median_price) OVER (
            PARTITION BY id
            ORDER BY week_start
        ) - 1 AS median_basis_return
    FROM weekly_prices
),

valid_returns AS (
    SELECT
        id,
        name,
        family,
        rarity,
        week_start,
        mean_basis_return,
        median_basis_return
    FROM weekly_returns
    WHERE
        mean_basis_return IS NOT NULL
        AND median_basis_return IS NOT NULL
),

winsorized AS (
    SELECT
        id,
        name,
        family,
        rarity,
        week_start,
        least(
            greatest(mean_basis_return, -return_cap()), return_cap()
        ) AS mean_basis_return,
        least(
            greatest(median_basis_return, -return_cap()), return_cap()
        ) AS median_basis_return
    FROM valid_returns
),

with_ratios AS (
    SELECT
        id,
        name,
        family,
        rarity,
        week_start,
        mean_basis_return,
        median_basis_return,
        avg(mean_basis_return) OVER (PARTITION BY id) AS avg_return,
        stddev(mean_basis_return) OVER (PARTITION BY id) AS std_return,
        avg(
            CASE
                WHEN mean_basis_return < 0
                    THEN mean_basis_return * mean_basis_return
                ELSE 0
            END
        ) OVER (PARTITION BY id) AS semivariance
    FROM winsorized
)

SELECT
    week_start,
    id,
    name,
    family,
    rarity,
    mean_basis_return AS mean_return,
    median_basis_return AS median_return,
    avg_return / nullif(std_return, 0) AS sharpe,
    avg_return / nullif(sqrt(semivariance), 0) AS sortino
FROM with_ratios;

ALTER TABLE cleaned.returns RENAME COLUMN week_start TO week;
