-- This query counts portfolio-week rows in portfolios.buy_and_hold.
-- The portfolio command uses this result after it creates the portfolio.

SELECT count(*) FROM portfolios.buy_and_hold
