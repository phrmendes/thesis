-- This query counts rows in raw.prices. The data build and data join commands
-- use this result to validate table creation and preserve row counts.

SELECT count(*) FROM raw.prices
