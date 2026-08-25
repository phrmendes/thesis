CREATE OR REPLACE TABLE items AS
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
    max(market_hash_name) AS item_name,
    max(rarity) AS rarity
FROM source
WHERE
    market_hash_name IS NOT NULL
    AND trim(market_hash_name) <> ''
GROUP BY sha256(market_hash_name)
