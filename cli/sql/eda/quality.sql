WITH stats AS (
    SELECT
        count(*) AS records,
        count(DISTINCT id) AS assets,
        count(DISTINCT week) AS weeks,
        count(*) FILTER (WHERE mean_return > 0) AS positive_weeks,
        count(*) FILTER (WHERE mean_return < 0) AS negative_weeks,
        count(*) FILTER (WHERE sharpe IS NOT NULL) AS with_sharpe
    FROM returns
),

per_asset AS (
    SELECT count(week) AS n_weeks
    FROM returns
    GROUP BY id
)

SELECT
    'records' AS metric_name,
    cast(records AS VARCHAR) AS metric_value
FROM stats
UNION ALL
SELECT
    'assets' AS metric_name,
    cast(assets AS VARCHAR) AS metric_value
FROM stats
UNION ALL
SELECT
    'weeks' AS metric_name,
    cast(weeks AS VARCHAR) AS metric_value
FROM stats
UNION ALL
SELECT
    'min_weeks_per_asset' AS metric_name,
    cast(min(n_weeks) AS VARCHAR) AS metric_value
FROM per_asset
UNION ALL
SELECT
    'avg_weeks_per_asset' AS metric_name,
    cast(round(avg(n_weeks), 1) AS VARCHAR) AS metric_value
FROM per_asset
UNION ALL
SELECT
    'max_weeks_per_asset' AS metric_name,
    cast(max(n_weeks) AS VARCHAR) AS metric_value
FROM per_asset
UNION ALL
SELECT
    'positive_return_weeks' AS metric_name,
    cast(positive_weeks AS VARCHAR) AS metric_value
FROM stats
UNION ALL
SELECT
    'negative_return_weeks' AS metric_name,
    cast(negative_weeks AS VARCHAR) AS metric_value
FROM stats
UNION ALL
SELECT
    'records_with_sharpe' AS metric_name,
    cast(with_sharpe AS VARCHAR) AS metric_value
FROM stats
