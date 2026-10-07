-- ============================================================================
-- CreditPulse: Digital Lending & Credit Risk Warehouse Schema
-- Dialect: ANSI SQL / Compatible with SQLite, PostgreSQL, DuckDB, BigQuery
-- ============================================================================

DROP TABLE IF EXISTS fact_bureau_inquiries;
DROP TABLE IF EXISTS fact_repayment_schedule;
DROP TABLE IF EXISTS fact_loan_originations;
DROP TABLE IF EXISTS dim_loan_products;
DROP TABLE IF EXISTS dim_borrowers;

-- ----------------------------------------------------------------------------
-- 1. Dimension: Borrowers (Underwriting Profile & Demographics)
-- ----------------------------------------------------------------------------
CREATE TABLE dim_borrowers (
    borrower_id VARCHAR(50) PRIMARY KEY,
    age INT NOT NULL,
    gender VARCHAR(10) NOT NULL,
    employment_type VARCHAR(50) NOT NULL,        -- Salaried Corporate, Salaried SME, Self-Employed, Gig
    monthly_income_inr DECIMAL(12, 2) NOT NULL,
    cibil_score INT NOT NULL,                    -- 300 to 900
    city VARCHAR(50) NOT NULL,
    city_tier VARCHAR(20) NOT NULL,              -- Tier 1, Tier 2, Tier 3
    state VARCHAR(50) NOT NULL,
    residence_ownership VARCHAR(40) NOT NULL,    -- Owned, Rented, Family
    bureau_total_accounts INT NOT NULL,
    bureau_active_loans_count INT NOT NULL,
    total_existing_monthly_emi DECIMAL(10, 2) NOT NULL,
    debt_to_income_ratio DECIMAL(5, 4) NOT NULL, -- Existing EMI / Monthly Income
    credit_utilization_ratio DECIMAL(5, 4) NOT NULL,
    bureau_inquiries_last_30d INT NOT NULL,
    bureau_inquiries_last_90d INT NOT NULL,
    historical_dpd_max_last_12m INT NOT NULL,
    created_at DATE NOT NULL
);

-- ----------------------------------------------------------------------------
-- 2. Dimension: Loan Products (Master Offering & Policy Parameters)
-- ----------------------------------------------------------------------------
CREATE TABLE dim_loan_products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    product_category VARCHAR(50) NOT NULL,       -- Personal Loan, BNPL, Vehicle Loan, MSME, Mortgage
    secured_flag INT NOT NULL DEFAULT 0,         -- 0 = Unsecured, 1 = Secured
    annual_interest_rate_pct DECIMAL(5, 2) NOT NULL,
    default_tenor_months INT NOT NULL,
    min_cibil_threshold INT NOT NULL
);

-- ----------------------------------------------------------------------------
-- 3. Fact: Loan Originations (Core Loan Tape & Snapshot)
-- ----------------------------------------------------------------------------
CREATE TABLE fact_loan_originations (
    loan_id VARCHAR(50) PRIMARY KEY,
    borrower_id VARCHAR(50) NOT NULL,
    product_id VARCHAR(50) NOT NULL,
    origination_date DATE NOT NULL,
    disbursed_principal_inr DECIMAL(12, 2) NOT NULL,
    annual_interest_rate DECIMAL(5, 2) NOT NULL,
    tenor_months INT NOT NULL,
    monthly_emi_inr DECIMAL(10, 2) NOT NULL,
    total_receivable_inr DECIMAL(12, 2) NOT NULL,
    loan_purpose VARCHAR(50) NOT NULL,
    
    -- Current Status & Default Flags
    loan_status VARCHAR(40) NOT NULL,            -- Active, Fully Paid, Defaulted / Written-Off
    current_dpd INT NOT NULL DEFAULT 0,          -- Current Days Past Due
    current_delinquency_bucket VARCHAR(30) NOT NULL, -- Current, 1-30 DPD, 31-60 DPD, 61-90 DPD, 90+ DPD
    is_default_flag INT NOT NULL DEFAULT 0,      -- 1 if current_dpd >= 90 or Defaulted
    default_date DATE,
    
    -- Balances & Exposure at Default (EAD)
    total_principal_paid DECIMAL(12, 2) NOT NULL DEFAULT 0.0,
    total_interest_paid DECIMAL(12, 2) NOT NULL DEFAULT 0.0,
    outstanding_balance_inr DECIMAL(12, 2) NOT NULL, -- EAD Exposure at Default
    
    FOREIGN KEY (borrower_id) REFERENCES dim_borrowers(borrower_id),
    FOREIGN KEY (product_id) REFERENCES dim_loan_products(product_id)
);

-- ----------------------------------------------------------------------------
-- 4. Fact: Repayment Schedule & Monthly Performance Ledger
-- ----------------------------------------------------------------------------
CREATE TABLE fact_repayment_schedule (
    schedule_id VARCHAR(60) PRIMARY KEY,
    loan_id VARCHAR(50) NOT NULL,
    installment_number INT NOT NULL,             -- Month on Book (MOB)
    due_date DATE NOT NULL,
    repayment_month VARCHAR(7) NOT NULL,         -- YYYY-MM
    payment_date DATE,
    scheduled_emi_amount DECIMAL(10, 2) NOT NULL,
    paid_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.0,
    principal_component DECIMAL(10, 2) NOT NULL,
    interest_component DECIMAL(10, 2) NOT NULL,
    closing_balance_inr DECIMAL(12, 2) NOT NULL,
    dpd_days INT NOT NULL DEFAULT 0,
    delinquency_bucket VARCHAR(30) NOT NULL,     -- 0_Current, 1_DPD_1_30, 2_DPD_31_60, 3_DPD_61_90, 4_DPD_90_Plus
    installment_status VARCHAR(30) NOT NULL,     -- Paid_On_Time, Paid_Late, Missed_Delinquent, Written_Off
    FOREIGN KEY (loan_id) REFERENCES fact_loan_originations(loan_id)
);

-- ----------------------------------------------------------------------------
-- 5. Fact: Credit Bureau Inquiries (Hard Pulls prior to Origination)
-- ----------------------------------------------------------------------------
CREATE TABLE fact_bureau_inquiries (
    inquiry_id VARCHAR(60) PRIMARY KEY,
    borrower_id VARCHAR(50) NOT NULL,
    inquiry_date DATE NOT NULL,
    inquiry_purpose VARCHAR(50) NOT NULL,        -- Unsecured Personal Loan, Credit Card, BNPL, Vehicle Loan
    inquiry_lender_type VARCHAR(50) NOT NULL,    -- FinTech NBFC, Private Bank, PSU Bank
    amount_requested DECIMAL(12, 2) NOT NULL,
    FOREIGN KEY (borrower_id) REFERENCES dim_borrowers(borrower_id)
);

-- ----------------------------------------------------------------------------
-- High-Performance Analytical Indexes
-- ----------------------------------------------------------------------------
CREATE INDEX idx_loan_borrower ON fact_loan_originations(borrower_id);
CREATE INDEX idx_loan_orig_date ON fact_loan_originations(origination_date);
CREATE INDEX idx_loan_status ON fact_loan_originations(loan_status);
CREATE INDEX idx_loan_dpd ON fact_loan_originations(current_dpd);
CREATE INDEX idx_repay_loan_mob ON fact_repayment_schedule(loan_id, installment_number);
CREATE INDEX idx_repay_bucket ON fact_repayment_schedule(delinquency_bucket);
CREATE INDEX idx_repay_month ON fact_repayment_schedule(repayment_month);
CREATE INDEX idx_bureau_borrower ON fact_bureau_inquiries(borrower_id);
