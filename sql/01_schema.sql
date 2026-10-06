-- ============================================================================
-- RelateIQ — Schema DDL (Snowflake)
-- Hackathon: Snowflake CoCo CLI 2026, PS2. Author: Ratnesh Saxena (Solo).
-- Idempotent: safe to run repeatedly (CREATE IF NOT EXISTS everywhere,
-- ACTIONS_AUDIT handled by 04_audit.sql with CREATE TABLE IF NOT EXISTS).
-- Types mirror data/*.csv schemas EXACTLY. Currency: INR. Anchor date: 2026-10-06.
-- ============================================================================

-- Warehouse/role assumed from the caller's session (no hardcoded credentials).
CREATE DATABASE IF NOT EXISTS RELATEIQ_DEMO;
CREATE SCHEMA IF NOT EXISTS RELATEIQ_DEMO.OPS;

USE DATABASE RELATEIQ_DEMO;
USE SCHEMA OPS;

-- ----------------------------------------------------------------------------
-- CUSTOMERS — mirrors data/customers.csv (40 rows)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CUSTOMERS (
    customer_id        VARCHAR(20)  NOT NULL,  -- CUST-001 ... CUST-040
    name               VARCHAR(100) NOT NULL,
    segment            VARCHAR(30)  NOT NULL,  -- Salaried | Self-Employed | Small Business
    region             VARCHAR(30)  NOT NULL,  -- Mumbai, Delhi NCR, Bengaluru, Chennai, Pune, Hyderabad
    tenure_months      INTEGER      NOT NULL,  -- 3..84
    credit_score       INTEGER      NOT NULL,  -- 580..820
    credit_limit       INTEGER      NOT NULL,  -- 50000..2000000 INR
    utilization_pct    INTEGER      NOT NULL,  -- 5..98
    missed_payments_12m INTEGER     NOT NULL,  -- 0..8
    avg_days_late      INTEGER      NOT NULL,  -- 0..45
    products_held      INTEGER      NOT NULL,  -- 1..4
    lifetime_value     INTEGER      NOT NULL,  -- 10000..500000 INR
    behavior_profile   VARCHAR(20)  NOT NULL,  -- loyal | at-risk | delinquent | new | dormant | high-value
    contact_email      VARCHAR(120) NOT NULL,
    contact_phone      VARCHAR(30)  NOT NULL,  -- +91 98XXX XXXXX (synthetic)
    CONSTRAINT pk_customers PRIMARY KEY (customer_id)
);

-- ----------------------------------------------------------------------------
-- ACCOUNTS — mirrors data/accounts.csv (~70 rows)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ACCOUNTS (
    account_id        VARCHAR(20)  NOT NULL,  -- ACC-001 ...
    customer_id       VARCHAR(20)  NOT NULL,  -- FK -> CUSTOMERS
    product_type      VARCHAR(30)  NOT NULL,  -- Personal Loan | Credit Card | BNPL | Two-wheeler Loan | Gold Loan
    sanctioned_limit  INTEGER      NOT NULL,  -- INR
    outstanding       INTEGER      NOT NULL,  -- INR
    status            VARCHAR(20)  NOT NULL,  -- Active | Delinquent | Closed
    opened_date       DATE         NOT NULL,
    CONSTRAINT pk_accounts PRIMARY KEY (account_id),
    CONSTRAINT fk_accounts_customer FOREIGN KEY (customer_id) REFERENCES CUSTOMERS (customer_id)
);

-- ----------------------------------------------------------------------------
-- TRANSACTIONS — mirrors data/transactions.csv (~800 rows, last 90 days)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS TRANSACTIONS (
    txn_id     VARCHAR(20) NOT NULL,  -- TXN-0001 ...
    account_id VARCHAR(20) NOT NULL,  -- FK -> ACCOUNTS
    txn_date   DATE        NOT NULL,  -- 2026-07-08 ... 2026-10-06
    amount     INTEGER     NOT NULL,  -- INR
    category   VARCHAR(30) NOT NULL,  -- Shopping | Travel | Bills | Cash Withdrawal | EMI Debit
    channel    VARCHAR(20) NOT NULL,  -- App | POS | Online
    CONSTRAINT pk_transactions PRIMARY KEY (txn_id),
    CONSTRAINT fk_transactions_account FOREIGN KEY (account_id) REFERENCES ACCOUNTS (account_id)
);

-- ----------------------------------------------------------------------------
-- REPAYMENTS — mirrors data/repayments.csv (~400 rows)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS REPAYMENTS (
    repayment_id VARCHAR(20) NOT NULL,
    account_id   VARCHAR(20) NOT NULL,  -- FK -> ACCOUNTS
    due_date     DATE        NOT NULL,
    paid_date    DATE,                  -- NULL when unpaid
    amount_due   INTEGER     NOT NULL,  -- INR
    amount_paid  INTEGER     NOT NULL,  -- INR (0 when unpaid)
    days_late    INTEGER     NOT NULL,  -- max(0, (paid_date OR 2026-10-06) - due_date)
    CONSTRAINT pk_repayments PRIMARY KEY (repayment_id),
    CONSTRAINT fk_repayments_account FOREIGN KEY (account_id) REFERENCES ACCOUNTS (account_id)
);

-- ----------------------------------------------------------------------------
-- CALL_TRANSCRIPTS — one row per customer with a call transcript (customer_id, transcript_md)
-- Source: data/call_transcripts.md (~10 customers, ends with [SIGNAL: <signal>]).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CALL_TRANSCRIPTS (
    customer_id   VARCHAR(20) NOT NULL,  -- FK -> CUSTOMERS
    transcript_md VARCHAR(16777216) NOT NULL,  -- full markdown transcript incl. date + [SIGNAL: ...] tag
    CONSTRAINT fk_call_transcripts_customer FOREIGN KEY (customer_id) REFERENCES CUSTOMERS (customer_id)
);

-- ----------------------------------------------------------------------------
-- SUPPORT_EMAILS — one row per customer with an email thread (customer_id, thread_md)
-- Source: data/support_emails.md (~10 customers, ends with [SIGNAL: <signal>]).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS SUPPORT_EMAILS (
    customer_id VARCHAR(20) NOT NULL,  -- FK -> CUSTOMERS
    thread_md   VARCHAR(16777216) NOT NULL,  -- full markdown email thread incl. [SIGNAL: ...] tag
    CONSTRAINT fk_support_emails_customer FOREIGN KEY (customer_id) REFERENCES CUSTOMERS (customer_id)
);

-- ----------------------------------------------------------------------------
-- ACTIONS_AUDIT — append-only decision audit (full DDL + insert in 04_audit.sql).
-- Kept here as CREATE TABLE IF NOT EXISTS so 01_schema.sql stands alone;
-- 04_audit.sql uses the same statement (IF NOT EXISTS) and adds the append-only
-- comments and the demo INSERT.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ACTIONS_AUDIT (
    action_id        INTEGER       AUTOINCREMENT,
    decided_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    customer_id      VARCHAR(20)   NOT NULL,
    action           VARCHAR(30)   NOT NULL,  -- dispute-hold | churn-intervention | collections-firm
                                             -- | collections-gentle | retention-offer | upsell
    attention_score  INTEGER       NOT NULL,  -- 0..100
    opportunity_score INTEGER      NOT NULL,  -- 0..100
    reason           VARCHAR(4000) NOT NULL,
    message          VARCHAR(16777216),       -- outreach draft (NULL for dispute-hold)
    decided_by       VARCHAR(50)   DEFAULT 'relateiq-agent',
    CONSTRAINT pk_actions_audit PRIMARY KEY (action_id)
);
