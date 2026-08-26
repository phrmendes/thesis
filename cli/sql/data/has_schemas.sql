SELECT
    EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE
            table_schema = 'raw'
            AND table_name = 'prices'
    )
    AND EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE
            table_schema = 'cleaned'
            AND table_name = 'returns'
    ) AS schemas_migrated
