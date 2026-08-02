CREATE OR REPLACE TABLE prices AS
SELECT * FROM read_parquet('${data_dir}/*.parquet')
ORDER BY item_hash_name, date
