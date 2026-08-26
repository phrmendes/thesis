WITH asset_stats AS (
    SELECT
        cleaned_returns.id,
        cleaned_returns.name,
        avg(cleaned_returns.return) AS mean_return,
        median(cleaned_returns.return) AS median_return,
        min(cleaned_returns.return) AS min_return,
        max(cleaned_returns.return) AS max_return,
        stddev(cleaned_returns.return) AS std_return,
        stddev(
            CASE
                WHEN cleaned_returns.return < 0 THEN cleaned_returns.return
            END
        ) AS negative_returns_std,
        count(cleaned_returns.week) AS n_weeks,
        max(cleaned_returns.sharpe) AS sharpe,
        max(cleaned_returns.sortino) AS sortino
    FROM cleaned.returns AS cleaned_returns
    GROUP BY
        cleaned_returns.id,
        cleaned_returns.name
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
