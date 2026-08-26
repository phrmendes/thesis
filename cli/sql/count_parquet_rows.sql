-- This query counts daily parquet observations in ${data_dir}. The data build
-- command uses this result to validate the raw price table row count.

SELECT count(*) FROM read_parquet('${data_dir}/*.parquet')
