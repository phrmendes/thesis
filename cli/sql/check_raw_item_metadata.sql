-- This query checks if raw item metadata is available in the database. The data
-- fetch command uses this result to decide if it must download item metadata.

SELECT
    EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE
            table_schema = 'raw'
            AND table_name = 'items'
    )
    OR EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE
            table_schema = 'raw'
            AND table_name = 'prices'
            AND column_name = 'rarity'
    ) AS has_item_metadata
