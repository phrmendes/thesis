-- This query attaches item rarity from raw.items to raw.prices. It replaces the
-- raw price table after the join. The data join command uses this query.

CREATE TABLE raw.prices_joined AS
SELECT
    raw_prices.date,
    raw_prices.id,
    raw_prices.name,
    raw_prices.family,
    raw_prices.prices,
    item_metadata.rarity
FROM raw.prices AS raw_prices
LEFT JOIN raw.items AS item_metadata
    ON raw_prices.id = item_metadata.id;

DROP TABLE raw.prices;
DROP TABLE raw.items;
ALTER TABLE raw.prices_joined RENAME TO prices;
