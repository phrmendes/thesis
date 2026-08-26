-- This query groups assets by observed weekly return counts in cleaned.returns.
-- The EDA coverage command uses the result for the asset persistence table.

WITH week_counts AS (
    SELECT
        id,
        count(week) AS weeks
    FROM cleaned.returns
    GROUP BY id
),

buckets AS (
    SELECT
        CASE
            WHEN weeks < 25 THEN '< 25'
            WHEN weeks < 50 THEN '25-49'
            WHEN weeks < 75 THEN '50-74'
            WHEN weeks < 100 THEN '75-99'
            WHEN weeks < 125 THEN '100-124'
            ELSE '125+'
        END AS weeks_range,
        count(*) AS assets,
        round(avg(weeks), 0) AS avg_weeks
    FROM week_counts
    GROUP BY weeks_range
)

SELECT
    weeks_range,
    assets,
    avg_weeks
FROM buckets
ORDER BY
    CASE weeks_range
        WHEN '< 25' THEN 1
        WHEN '25-49' THEN 2
        WHEN '50-74' THEN 3
        WHEN '75-99' THEN 4
        WHEN '100-124' THEN 5
        ELSE 6
    END
