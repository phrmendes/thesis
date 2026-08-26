WITH stats AS (
    SELECT
        cast(
            date_diff('day', min(week), max(week)) / 7 + 1 AS INTEGER
        ) AS total_weeks,
        min(week) AS start_date,
        max(week) AS end_date,
        count(DISTINCT week) AS observed_weeks,
        round(
            count(DISTINCT week) * 100.0
            / cast(date_diff('day', min(week), max(week)) / 7 + 1 AS INTEGER),
            1
        ) AS coverage_pct,
        min(assets_per_week) AS min_assets_per_week,
        round(avg(assets_per_week), 0) AS avg_assets_per_week,
        max(assets_per_week) AS max_assets_per_week
    FROM (
        SELECT
            week,
            count(*) AS assets_per_week
        FROM returns
        GROUP BY week
    ) AS weekly_counts
)

SELECT
    'start_date' AS metric_name,
    strftime(start_date, '%d/%m/%Y') AS metric_value
FROM stats
UNION ALL
SELECT
    'end_date' AS metric_name,
    strftime(end_date, '%d/%m/%Y') AS metric_value
FROM stats
UNION ALL
SELECT
    'observed_weeks' AS metric_name,
    cast(observed_weeks AS VARCHAR) AS metric_value
FROM stats
UNION ALL
SELECT
    'total_weeks' AS metric_name,
    cast(total_weeks AS VARCHAR) AS metric_value
FROM stats
UNION ALL
SELECT
    'coverage' AS metric_name,
    concat(cast(coverage_pct AS VARCHAR), '%') AS metric_value
FROM stats
UNION ALL
SELECT
    'min_assets_per_week' AS metric_name,
    cast(min_assets_per_week AS VARCHAR) AS metric_value
FROM stats
UNION ALL
SELECT
    'avg_assets_per_week' AS metric_name,
    cast(avg_assets_per_week AS VARCHAR) AS metric_value
FROM stats
UNION ALL
SELECT
    'max_assets_per_week' AS metric_name,
    cast(max_assets_per_week AS VARCHAR) AS metric_value
FROM stats
