-- This query summarizes size, return signs, coverage, and metric availability.
-- It derives capped weekly returns from cleaned.prices. The EDA quality command
-- renders the result.

CREATE OR REPLACE MACRO return_cap() AS (1.0);

WITH weekly_returns AS (
    SELECT
        cleaned_prices.id,
        cleaned_prices.week,
        cleaned_prices.price / lag(cleaned_prices.price) OVER (
            PARTITION BY cleaned_prices.id
            ORDER BY cleaned_prices.week
        ) - 1 AS raw_return
    FROM cleaned.prices AS cleaned_prices
),

capped_returns AS (
    SELECT
        id,
        week,
        least(greatest(raw_return, -return_cap()), return_cap()) AS return_value
    FROM weekly_returns
    WHERE raw_return IS NOT NULL
),

price_stats AS (
    SELECT
        count(*) AS records,
        count(DISTINCT id) AS assets,
        count(DISTINCT week) AS weeks
    FROM cleaned.prices
),

return_stats AS (
    SELECT
        count(*) FILTER (WHERE return_value > 0) AS positive_weeks,
        count(*) FILTER (WHERE return_value < 0) AS negative_weeks
    FROM capped_returns
),

asset_week_counts AS (
    SELECT
        id,
        count(week) AS n_weeks
    FROM cleaned.prices
    GROUP BY id
),

asset_stats AS (
    SELECT
        min(n_weeks) AS min_weeks,
        round(avg(n_weeks), 1) AS avg_weeks,
        max(n_weeks) AS max_weeks
    FROM asset_week_counts
),

asset_metrics AS (
    SELECT
        id,
        avg(return_value) / nullif(stddev(return_value), 0) AS sharpe
    FROM capped_returns
    GROUP BY id
),

sharpe_stats AS (
    SELECT count(*) AS with_sharpe
    FROM asset_metrics
    WHERE sharpe IS NOT NULL
)

SELECT
    'records' AS metric_name,
    cast(records AS VARCHAR) AS metric_value
FROM price_stats
UNION ALL
SELECT
    'assets' AS metric_name,
    cast(assets AS VARCHAR) AS metric_value
FROM price_stats
UNION ALL
SELECT
    'weeks' AS metric_name,
    cast(weeks AS VARCHAR) AS metric_value
FROM price_stats
UNION ALL
SELECT
    'min_weeks_per_asset' AS metric_name,
    cast(min_weeks AS VARCHAR) AS metric_value
FROM asset_stats
UNION ALL
SELECT
    'avg_weeks_per_asset' AS metric_name,
    cast(avg_weeks AS VARCHAR) AS metric_value
FROM asset_stats
UNION ALL
SELECT
    'max_weeks_per_asset' AS metric_name,
    cast(max_weeks AS VARCHAR) AS metric_value
FROM asset_stats
UNION ALL
SELECT
    'positive_return_weeks' AS metric_name,
    cast(positive_weeks AS VARCHAR) AS metric_value
FROM return_stats
UNION ALL
SELECT
    'negative_return_weeks' AS metric_name,
    cast(negative_weeks AS VARCHAR) AS metric_value
FROM return_stats
UNION ALL
SELECT
    'records_with_sharpe' AS metric_name,
    cast(with_sharpe AS VARCHAR) AS metric_value
FROM sharpe_stats
