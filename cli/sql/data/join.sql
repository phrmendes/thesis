CREATE TABLE prices_joined AS
SELECT
    prices.date,
    prices.id,
    prices.name,
    prices.family,
    prices.prices,
    items.rarity
FROM prices
LEFT JOIN items
    ON prices.id = items.id
