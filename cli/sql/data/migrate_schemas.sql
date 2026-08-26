CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS cleaned;
CREATE SCHEMA IF NOT EXISTS strategy;

CREATE OR REPLACE TABLE raw.prices AS
SELECT
    date,
    id,
    name,
    family,
    prices,
    rarity
FROM main.prices_raw;

CREATE OR REPLACE TABLE cleaned.returns AS
SELECT
    week,
    id,
    name,
    family,
    rarity,
    mean_return,
    median_return,
    sharpe,
    sortino
FROM main.returns;

DROP TABLE main.prices_raw;
DROP TABLE main.returns;
DROP TABLE IF EXISTS main.buy_and_hold_selection;
DROP TABLE IF EXISTS main.buy_and_hold_assets;
DROP TABLE IF EXISTS main.buy_and_hold_portfolio_returns;
DROP TABLE IF EXISTS main.buy_and_hold_portfolio_summary;
