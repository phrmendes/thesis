-- This query creates raw.items from the item metadata JSON template parameter.
-- It retains one stable ID and one rarity value for each market name.
-- The data build command uses this table to attach metadata to raw prices.

CREATE SCHEMA IF NOT EXISTS raw;

CREATE OR REPLACE TABLE raw.items AS
WITH source AS (
    SELECT
        market_hash_name,
        nullif(
            trim(json_extract_string(to_json(rarity), '$$.name')),
            ''
        ) AS rarity
    FROM read_json_auto('${items_path}')
)

SELECT
    sha256(market_hash_name) AS id,
    max(rarity) AS rarity
FROM source
WHERE
    market_hash_name IS NOT NULL
    AND trim(market_hash_name) <> ''
GROUP BY sha256(market_hash_name)
