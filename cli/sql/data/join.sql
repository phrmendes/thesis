CREATE TABLE prices_joined AS
SELECT
    prices_raw.date,
    prices_raw.id,
    prices_raw.name,
    prices_raw.family,
    prices_raw.prices,
    items.rarity
FROM prices_raw
LEFT JOIN items
    ON prices_raw.id = items.id;

DROP TABLE prices_raw;
DROP TABLE items;
ALTER TABLE prices_joined RENAME TO prices_raw;
