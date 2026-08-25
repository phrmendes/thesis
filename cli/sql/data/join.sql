CREATE TABLE prices_joined AS
SELECT
    prices.date,
    prices.id,
    prices.name,
    prices.source_data,
    prices.steam_price,
    prices.buff163_price,
    prices.csgotrader_price,
    skins.rarity
FROM prices
LEFT JOIN skins
    ON prices.id = skins.id
