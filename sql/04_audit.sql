-- ============================================================================
-- RelateIQ — ACTIONS_AUDIT: append-only decision audit table (Snowflake)
-- Hackathon: Snowflake CoCo CLI 2026, PS2. Author: Ratnesh Saxena (Solo).
-- Every Next-Best-Action decision lands here with its scores, reasoning and
-- outreach draft — the compliance trail the demo's "Action Queue" tab reads.
-- ============================================================================

USE DATABASE RELATEIQ_DEMO;
USE SCHEMA OPS;

-- Append-only: INSERT + SELECT allowed, but no UPDATE/DELETE/REPLACE.
-- (Also present in 01_schema.sql via CREATE TABLE IF NOT EXISTS; repeated
-- here intentionally so 04_audit.sql is self-contained.)
CREATE TABLE IF NOT EXISTS ACTIONS_AUDIT (
    action_id        INTEGER       AUTOINCREMENT,
    decided_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    customer_id      VARCHAR(20)   NOT NULL,
    action           VARCHAR(30)   NOT NULL,  -- dispute-hold | churn-intervention
                                             -- | collections-firm | collections-gentle
                                             -- | retention-offer | upsell
    attention_score  INTEGER       NOT NULL,  -- 0..100, higher = needs attention now
    opportunity_score INTEGER      NOT NULL,  -- 0..100, higher = growth potential
    reason           VARCHAR(4000) NOT NULL,  -- why this branch fired
    message          VARCHAR(16777216),       -- outreach draft (NULL for dispute-hold)
    decided_by       VARCHAR(50)   DEFAULT 'relateiq-agent',
    CONSTRAINT pk_actions_audit PRIMARY KEY (action_id)
);

-- Append-only grant comments:
-- Grant ONLY INSERT and SELECT to the application role. Deliberately DO NOT
-- grant UPDATE, DELETE, TRUNCATE, or OWNERSHIP transfer, so audit rows can
-- never be edited or removed once written. Only the table owner (or a DBA
-- role with MANAGE GRANTS) can alter this policy.
COMMENT ON TABLE ACTIONS_AUDIT IS 'RelateIQ append-only decision audit. Application roles get INSERT + SELECT only; UPDATE/DELETE are never granted.';

-- ----------------------------------------------------------------------------
-- Sample INSERT: the demo's canonical retention-offer decision for Rohan Khanna
-- (story anchor: high-value, 60m tenure, 92% utilization, 3 recent misses,
-- recent complaint -> retention-offer). Mirrors one row of data/audit_log.csv.
-- ----------------------------------------------------------------------------
INSERT INTO ACTIONS_AUDIT (
    customer_id, action, attention_score, opportunity_score, reason, message, decided_by
) VALUES (
    'CUST-001',
    'retention-offer',
    68,
    42,
    'Attention 68 (High): utilization stress 92% (+15), 3 missed payments (+10), complaint signal (+8), credit deterioration (+4), dormancy (+3). No open dispute, DPD 0 -> retention-offer branch.',
    'Dear Rohan, this is Arjun Mehta, your Relationship Manager. I have noticed your recent experience has not been up to the mark, and I would like to make it right. We are waiving your next month''s card fee and reducing your interest rate by 1.5% for the next 6 months as a gesture of goodwill. I am personally available on call to discuss this. Regards, Arjun Mehta.',
    'relateiq-agent'
);
