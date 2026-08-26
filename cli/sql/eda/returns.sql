WITH asset_stats AS (
    SELECT
        id,
        name,
        family,
        rarity,
        avg(mean_return) AS mean_return,
        median(mean_return) AS median_return,
        min(mean_return) AS min_return,
        max(mean_return) AS max_return,
        stddev(mean_return) AS std_return,
        stddev(
            CASE WHEN mean_return < 0 THEN mean_return END
        ) AS negative_returns_std,
        count(week) AS n_weeks,
        max(sharpe) AS sharpe,
        max(sortino) AS sortino
    FROM returns
    GROUP BY id, name, family, rarity
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
