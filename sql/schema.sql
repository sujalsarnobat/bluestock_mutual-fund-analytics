-- =============================================================
--  schema.sql — Bluestock Fintech Mutual Fund Analytics DB
--  Star Schema: 2 dimension tables + 6 fact tables
--  Database: SQLite (compatible with PostgreSQL with minor edits)
-- =============================================================

-- ── Drop tables if re-creating ────────────────────────────────
DROP TABLE IF EXISTS fact_sip_industry;
DROP TABLE IF EXISTS fact_aum;
DROP TABLE IF EXISTS fact_portfolio;
DROP TABLE IF EXISTS fact_performance;
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS fact_nav;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_fund;


-- ── DIMENSION: dim_fund ───────────────────────────────────────
-- Master list of 40 mutual fund schemes
CREATE TABLE dim_fund (
    amfi_code           TEXT        PRIMARY KEY,
    fund_house          TEXT        NOT NULL,
    scheme_name         TEXT        NOT NULL,
    category            TEXT,                       -- Equity / Debt / Hybrid
    sub_category        TEXT,                       -- Large Cap / Mid Cap / etc.
    plan                TEXT,                       -- Regular / Direct
    launch_date         DATE,
    benchmark           TEXT,
    expense_ratio_pct   REAL,
    exit_load_pct       REAL,
    fund_manager        TEXT,
    risk_category       TEXT,                       -- Low / Moderate / High / Very High
    sebi_category_code  TEXT
);

CREATE INDEX idx_dim_fund_house     ON dim_fund(fund_house);
CREATE INDEX idx_dim_fund_category  ON dim_fund(category);


-- ── DIMENSION: dim_date ───────────────────────────────────────
-- Date spine for time-based joins
CREATE TABLE dim_date (
    date_id     INTEGER     PRIMARY KEY,    -- YYYYMMDD integer key
    date        DATE        NOT NULL UNIQUE,
    year        INTEGER,
    quarter     INTEGER,                    -- 1-4
    month       INTEGER,                    -- 1-12
    month_name  TEXT,
    week        INTEGER,                    -- ISO week number
    day_of_week INTEGER,                    -- 0=Mon … 6=Sun
    is_weekday  INTEGER,                    -- 1 = Mon-Fri, 0 = Sat/Sun
    is_month_end INTEGER                    -- 1 if last business day of month
);

CREATE INDEX idx_dim_date_year_month ON dim_date(year, month);


-- ── FACT: fact_nav ────────────────────────────────────────────
-- Daily NAV for every scheme (46 000+ rows)
CREATE TABLE fact_nav (
    nav_id              INTEGER     PRIMARY KEY AUTOINCREMENT,
    amfi_code           TEXT        NOT NULL REFERENCES dim_fund(amfi_code),
    nav_date            DATE        NOT NULL,
    nav                 REAL        NOT NULL CHECK (nav > 0),
    daily_return_pct    REAL                    -- (NAV_t / NAV_{t-1} - 1) * 100
);

CREATE INDEX idx_fact_nav_code_date ON fact_nav(amfi_code, nav_date);
CREATE INDEX idx_fact_nav_date      ON fact_nav(nav_date);


-- ── FACT: fact_transactions ───────────────────────────────────
-- Investor SIP / Lumpsum / Redemption transactions (32 000+ rows)
CREATE TABLE fact_transactions (
    tx_id               TEXT        PRIMARY KEY,
    investor_id         TEXT        NOT NULL,
    amfi_code           TEXT        NOT NULL REFERENCES dim_fund(amfi_code),
    transaction_date    DATE        NOT NULL,
    transaction_type    TEXT        NOT NULL CHECK (transaction_type IN ('SIP','Lumpsum','Redemption')),
    amount_inr          REAL        NOT NULL CHECK (amount_inr > 0),
    state               TEXT,
    city                TEXT,
    city_tier           TEXT,                   -- T30 / B30
    age_group           TEXT,
    gender              TEXT,
    annual_income_lakh  REAL,
    payment_mode        TEXT,
    kyc_status          TEXT
);

CREATE INDEX idx_fact_tx_investor   ON fact_transactions(investor_id);
CREATE INDEX idx_fact_tx_code       ON fact_transactions(amfi_code);
CREATE INDEX idx_fact_tx_date       ON fact_transactions(transaction_date);
CREATE INDEX idx_fact_tx_state      ON fact_transactions(state);


-- ── FACT: fact_performance ────────────────────────────────────
-- Pre-computed risk-return metrics per scheme (40 rows)
CREATE TABLE fact_performance (
    perf_id             INTEGER     PRIMARY KEY AUTOINCREMENT,
    amfi_code           TEXT        NOT NULL REFERENCES dim_fund(amfi_code),
    as_of_date          DATE,
    return_1yr_pct      REAL,
    return_3yr_pct      REAL,
    return_5yr_pct      REAL,
    benchmark_3yr_pct   REAL,
    alpha               REAL,
    beta                REAL,
    sharpe_ratio        REAL,
    sortino_ratio       REAL,
    std_dev_ann_pct     REAL,
    max_drawdown_pct    REAL,
    morningstar_rating  INTEGER
);

CREATE INDEX idx_fact_perf_code ON fact_performance(amfi_code);


-- ── FACT: fact_portfolio ──────────────────────────────────────
-- Top equity holdings per scheme (~320 rows)
CREATE TABLE fact_portfolio (
    holding_id          INTEGER     PRIMARY KEY AUTOINCREMENT,
    amfi_code           TEXT        NOT NULL REFERENCES dim_fund(amfi_code),
    as_of_date          DATE,
    stock_symbol        TEXT,
    stock_name          TEXT,
    sector              TEXT,
    weight_pct          REAL        CHECK (weight_pct BETWEEN 0 AND 100)
);

CREATE INDEX idx_fact_portfolio_code    ON fact_portfolio(amfi_code);
CREATE INDEX idx_fact_portfolio_sector  ON fact_portfolio(sector);


-- ── FACT: fact_aum ────────────────────────────────────────────
-- Quarterly AUM per fund house (~90 rows)
CREATE TABLE fact_aum (
    aum_id          INTEGER     PRIMARY KEY AUTOINCREMENT,
    fund_house      TEXT        NOT NULL,
    quarter_end     DATE        NOT NULL,
    year            INTEGER,
    quarter         INTEGER,
    aum_crore       REAL        NOT NULL CHECK (aum_crore >= 0),
    num_schemes     INTEGER
);

CREATE INDEX idx_fact_aum_house ON fact_aum(fund_house);
CREATE INDEX idx_fact_aum_date  ON fact_aum(quarter_end);


-- ── FACT: fact_sip_industry ───────────────────────────────────
-- Monthly industry-level SIP statistics (48 rows)
CREATE TABLE fact_sip_industry (
    sip_id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    month                       DATE    NOT NULL UNIQUE,
    sip_inflow_crore            REAL,
    active_sip_accounts_crore   REAL,
    new_sip_accounts_lakh       REAL,
    sip_aum_lakh_crore          REAL,
    yoy_growth_pct              REAL
);

CREATE INDEX idx_fact_sip_month ON fact_sip_industry(month);