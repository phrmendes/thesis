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
    sha256(item_hash_name) AS id,
    item_hash_name AS item_name,
    normalize_skin_name(item_hash_name) AS family_name,
    struct_pack(
        steam := steam_price,
        buff163 := buff163_price,
        csgotrader := csgotrader_price
    ) AS prices
FROM read_parquet('${data_dir}/*.parquet')
WHERE
    item_hash_name IS NOT NULL
    AND trim(item_hash_name) <> ''
ORDER BY item_hash_name, date;

ALTER TABLE prices RENAME COLUMN item_name TO name;
ALTER TABLE prices RENAME COLUMN family_name TO family;
