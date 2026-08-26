-- This query summarizes weekly returns derived from cleaned.prices.
-- It reports the ten highest mean-return assets and aggregate risk metrics.
-- The EDA returns command renders the result as a table.

CREATE OR REPLACE MACRO return_cap() AS (1.0);

WITH weekly_returns AS (
    SELECT
        cleaned_prices.id,
        cleaned_prices.name,
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
        name,
        week,
        least(greatest(raw_return, -return_cap()), return_cap()) AS return_value
    FROM weekly_returns
    WHERE raw_return IS NOT NULL
),

asset_metric_rows AS (
    SELECT
        id,
        name,
        week,
        return_value,
        avg(return_value) OVER (PARTITION BY id) AS average_return,
        stddev(return_value) OVER (PARTITION BY id) AS return_stddev,
        avg(
            CASE
                WHEN return_value < 0 THEN return_value * return_value
                ELSE 0
            END
        ) OVER (PARTITION BY id) AS return_semivariance
    FROM capped_returns
),

asset_stats AS (
    SELECT
        id,
        name,
        avg(return_value) AS mean_return,
        median(return_value) AS median_return,
        min(return_value) AS min_return,
        max(return_value) AS max_return,
        stddev(return_value) AS std_return,
        stddev(
            CASE WHEN return_value < 0 THEN return_value END
        ) AS negative_returns_std,
        count(week) AS n_weeks,
        max(average_return / nullif(return_stddev, 0)) AS sharpe,
        max(
            average_return / nullif(sqrt(return_semivariance), 0)
        ) AS sortino
    FROM asset_metric_rows
    GROUP BY id, name
),

ranked AS (
    SELECT
        *,
        row_number() OVER (ORDER BY mean_return DESC) AS rank_n
    FROM asset_stats
),

top10 AS (
    SELECT
        name,
        rank_n,
        mean_return,
        median_return,
        min_return,
        max_return,
        std_return,
        negative_returns_std,
        n_weeks,
        sharpe,
        sortino
    FROM ranked
    WHERE rank_n <= 10
),

other_assets AS (
    SELECT
        'rest' AS segment,
        NULL AS rank_n,
        avg(mean_return) AS mean_return,
        median(median_return) AS median_return,
        min(min_return) AS min_return,
        max(max_return) AS max_return,
        avg(std_return) AS std_return,
        avg(negative_returns_std) AS negative_returns_std,
        avg(n_weeks) AS n_weeks,
        avg(sharpe) AS sharpe,
        avg(sortino) AS sortino
    FROM ranked
    WHERE rank_n > 10
),

overall AS (
    SELECT
        'overall' AS segment,
        NULL AS rank_n,
        avg(mean_return) AS mean_return,
        median(median_return) AS median_return,
        min(min_return) AS min_return,
        max(max_return) AS max_return,
        avg(std_return) AS std_return,
        avg(negative_returns_std) AS negative_returns_std,
        avg(n_weeks) AS n_weeks,
        avg(sharpe) AS sharpe,
        avg(sortino) AS sortino
    FROM asset_stats
)

SELECT
    name,
    rank_n,
    mean_return,
    median_return,
    min_return,
    max_return,
    std_return,
    negative_returns_std,
    n_weeks,
    sharpe,
    sortino
FROM top10
UNION ALL
SELECT
    segment,
    rank_n,
    mean_return,
    median_return,
    min_return,
    max_return,
    std_return,
    negative_returns_std,
    n_weeks,
    sharpe,
    sortino
FROM other_assets
UNION ALL
SELECT
    segment,
    rank_n,
    mean_return,
    median_return,
    min_return,
    max_return,
    std_return,
    negative_returns_std,
    n_weeks,
    sharpe,
    sortino
FROM overall
ORDER BY rank_n NULLS LAST
