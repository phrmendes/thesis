CREATE OR REPLACE TABLE skins AS
WITH source AS (
    SELECT
        market_hash_name,
        nullif(
            trim(json_extract_string(to_json(rarity), '$$.name')),
            ''
        ) AS rarity
    FROM read_json_auto('${items_path}')
)

SELECT DISTINCT
    sha256(normalize_skin_name(market_hash_name)) AS id,
    rarity
FROM source
WHERE
    market_hash_name IS NOT NULL
    AND rarity IS NOT NULL
