CREATE OR REPLACE MACRO normalize_skin_name(item_name) AS (
    regexp_replace(
        regexp_replace(
            regexp_replace(trim(item_name), '^Souvenir ', ''),
            '^StatTrak™ ',
            ''
        ),
        ' \([^)]*\)$$',
        ''
    )
);

CREATE OR REPLACE TABLE prices AS
SELECT
    date,
    sha256(normalize_skin_name(item_hash_name)) AS id,
    normalize_skin_name(item_hash_name) AS item_name,
    source_data,
    CASE WHEN steam_price > 0 THEN steam_price END AS steam_price,
    CASE WHEN buff163_price > 0 THEN buff163_price END AS buff163_price,
    CASE WHEN csgotrader_price > 0 THEN csgotrader_price END AS csgotrader_price
FROM read_parquet('${data_dir}/*.parquet')
WHERE
    item_hash_name IS NOT NULL
    AND trim(item_hash_name) <> ''
ORDER BY item_hash_name, date;

ALTER TABLE prices RENAME COLUMN item_name TO name;
