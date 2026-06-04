-- =============================================================
--  queries.sql — Bluestock Fintech MF Analytics
--  10 analytical SQL queries (Day 2, Task 6)
--  Run against: bluestock_mf.db (SQLite)
-- =============================================================


-- ── Query 1: Top 5 Fund Houses by Latest AUM ─────────────────
-- Shows which AMCs manage the most assets
SELECT
    fund_house,
    ROUND(aum_crore / 100000.0, 2)  AS aum_lakh_crore,
    num_schemes
FROM fact_aum
WHERE quarter_end = (SELECT MAX(quarter_end) FROM fact_aum)
ORDER BY aum_crore DESC
LIMIT 5;


-- ── Query 2: Average NAV per Month for a Fund ────────────────
-- Replace '125497' with any amfi_code; useful for trend analysis
SELECT
    strftime('%Y-%m', nav_date)     AS year_month,
    ROUND(AVG(nav), 4)              AS avg_nav,
    ROUND(MIN(nav), 4)              AS min_nav,
    ROUND(MAX(nav), 4)              AS max_nav
FROM fact_nav
WHERE amfi_code = '125497'          -- HDFC Top 100 Direct
GROUP BY year_month
ORDER BY year_month;


-- ── Query 3: SIP Inflow YoY Growth ───────────────────────────
-- Compares each month's SIP inflow to same month prior year
SELECT
    strftime('%Y-%m', month)        AS month,
    sip_inflow_crore,
    ROUND(yoy_growth_pct, 2)        AS yoy_growth_pct
FROM fact_sip_industry
ORDER BY month;


-- ── Query 4: Total Transaction Amount by State ───────────────
-- Identifies top states by SIP / Lumpsum investment volume
SELECT
    state,
    COUNT(*)                                    AS num_transactions,
    ROUND(SUM(amount_inr) / 1e7, 2)            AS total_invested_crore,
    ROUND(AVG(amount_inr), 0)                  AS avg_amount_inr
FROM fact_transactions
WHERE transaction_type IN ('SIP', 'Lumpsum')
GROUP BY state
ORDER BY total_invested_crore DESC;


-- ── Query 5: Funds with Expense Ratio Below 1% ───────────────
-- Low-cost funds — better for long-term wealth creation
SELECT
    f.amfi_code,
    f.scheme_name,
    f.fund_house,
    f.category,
    f.expense_ratio_pct
FROM dim_fund f
WHERE f.expense_ratio_pct < 1.0
ORDER BY f.expense_ratio_pct ASC;


-- ── Query 6: Best Performing Funds by 3-Year CAGR ────────────
-- Risk-adjusted ranking using Sharpe ratio as tiebreaker
SELECT
    f.scheme_name,
    f.fund_house,
    f.sub_category,
    ROUND(p.return_3yr_pct, 2)      AS cagr_3yr_pct,
    ROUND(p.sharpe_ratio, 3)        AS sharpe,
    ROUND(p.alpha, 3)               AS alpha
FROM fact_performance p
JOIN dim_fund f ON f.amfi_code = p.amfi_code
ORDER BY p.return_3yr_pct DESC
LIMIT 10;


-- ── Query 7: SIP vs Lumpsum vs Redemption Split ──────────────
-- Shows investor behaviour breakdown by transaction type
SELECT
    transaction_type,
    COUNT(*)                                AS num_transactions,
    ROUND(SUM(amount_inr) / 1e7, 2)        AS total_crore,
    ROUND(AVG(amount_inr), 0)              AS avg_amount_inr,
    ROUND(COUNT(*) * 100.0 /
          SUM(COUNT(*)) OVER (), 1)        AS pct_of_total
FROM fact_transactions
GROUP BY transaction_type
ORDER BY total_crore DESC;


-- ── Query 8: Monthly NAV Volatility (Std Dev) ────────────────
-- Funds with highest intra-month NAV fluctuation signal higher risk
SELECT
    f.scheme_name,
    f.sub_category,
    strftime('%Y-%m', n.nav_date)           AS year_month,
    ROUND(AVG(n.daily_return_pct), 4)      AS avg_daily_return,
    COUNT(*)                                AS trading_days
FROM fact_nav n
JOIN dim_fund f ON f.amfi_code = n.amfi_code
WHERE n.nav_date >= DATE('now', '-12 months')
GROUP BY f.amfi_code, year_month
ORDER BY f.scheme_name, year_month;


-- ── Query 9: T30 vs B30 City Investment Comparison ───────────
-- AMFI classification: T30 = Top 30 cities, B30 = Beyond Top 30
SELECT
    city_tier,
    COUNT(DISTINCT investor_id)             AS unique_investors,
    COUNT(*)                                AS transactions,
    ROUND(SUM(amount_inr) / 1e7, 2)        AS total_invested_crore,
    ROUND(AVG(amount_inr), 0)              AS avg_sip_amount
FROM fact_transactions
GROUP BY city_tier
ORDER BY total_invested_crore DESC;


-- ── Query 10: Fund Scorecard — Composite Ranking ─────────────
-- Weighted rank: 3yr return (30%) + Sharpe (25%) + Alpha (20%)
--              + Expense ratio inverse (15%) + Max DD inverse (10%)
WITH ranked AS (
    SELECT
        p.amfi_code,
        f.scheme_name,
        f.sub_category,
        p.return_3yr_pct,
        p.sharpe_ratio,
        p.alpha,
        f.expense_ratio_pct,
        p.max_drawdown_pct,
        RANK() OVER (ORDER BY p.return_3yr_pct DESC)       AS rk_return,
        RANK() OVER (ORDER BY p.sharpe_ratio DESC)         AS rk_sharpe,
        RANK() OVER (ORDER BY p.alpha DESC)                AS rk_alpha,
        RANK() OVER (ORDER BY f.expense_ratio_pct ASC)     AS rk_expense,
        RANK() OVER (ORDER BY p.max_drawdown_pct DESC)     AS rk_drawdown
    FROM fact_performance p
    JOIN dim_fund f ON f.amfi_code = p.amfi_code
)
SELECT
    amfi_code,
    scheme_name,
    sub_category,
    ROUND(
        0.30 * rk_return  +
        0.25 * rk_sharpe  +
        0.20 * rk_alpha   +
        0.15 * rk_expense +
        0.10 * rk_drawdown, 2
    )                                       AS composite_score,
    ROUND(return_3yr_pct, 2)               AS cagr_3yr,
    ROUND(sharpe_ratio, 3)                 AS sharpe,
    ROUND(alpha, 3)                        AS alpha
FROM ranked
ORDER BY composite_score ASC               -- lower rank = better fund
LIMIT 10;