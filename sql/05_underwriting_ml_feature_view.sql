-- ==============================================================================
-- CREDITPULSE LENDING ANALYTICS
-- Script: 05_underwriting_ml_feature_view.sql
-- Description: Machine Learning Feature Store & Training Dataset View.
-- Joins borrower demographics, bureau history, loan terms, and derived risk ratios
-- with a zero-leakage 12-Month Default Label (90+ DPD within MOB <= 12).
-- ==============================================================================

DROP VIEW IF EXISTS view_underwriting_ml_features;

CREATE VIEW view_underwriting_ml_features AS
WITH first_12m_delinquency AS (
    -- Evaluate default status (90+ DPD) within the first 12 months of origination
    SELECT
        loan_id,
        MAX(dpd_days) AS max_dpd_first_12m,
        MAX(CASE WHEN dpd_days >= 90 THEN 1 ELSE 0 END) AS is_default_12m,
        COUNT(DISTINCT repayment_month) AS observed_months_on_book
    FROM fact_repayment_schedule
    WHERE installment_number <= 12
    GROUP BY loan_id
),

bureau_inquiries_agg AS (
    -- Pre-origination credit seeking behavior
    SELECT
        borrower_id,
        COUNT(inquiry_id) AS total_bureau_inquiries,
        SUM(CASE WHEN inquiry_purpose = 'Unsecured Personal Loan' THEN 1 ELSE 0 END) AS personal_loan_inquiries,
        SUM(CASE WHEN inquiry_purpose = 'Credit Card' THEN 1 ELSE 0 END) AS credit_card_inquiries
    FROM fact_bureau_inquiries
    GROUP BY borrower_id
)

SELECT
    -- Identifiers & Metadata
    l.loan_id,
    l.borrower_id,
    l.origination_date,
    strftime('%Y-%m', l.origination_date) AS origination_cohort,
    
    -- Product Information
    p.product_id,
    p.product_name,
    p.product_category,
    p.secured_flag,
    
    -- Loan Characteristics
    l.disbursed_principal_inr,
    l.tenor_months,
    l.annual_interest_rate,
    l.monthly_emi_inr,
    l.loan_purpose,
    l.outstanding_balance_inr AS current_outstanding_inr,
    
    -- Borrower Demographics & Financials
    b.age,
    b.gender,
    b.employment_type,
    b.monthly_income_inr,
    b.city,
    b.city_tier,
    b.state,
    b.residence_ownership,
    
    -- Credit Bureau Features (Origination Snapshot)
    b.cibil_score,
    b.bureau_total_accounts,
    b.bureau_active_loans_count,
    b.total_existing_monthly_emi,
    b.debt_to_income_ratio,
    b.credit_utilization_ratio,
    b.bureau_inquiries_last_30d,
    b.bureau_inquiries_last_90d,
    b.historical_dpd_max_last_12m,
    
    -- Bureau Inquiry Aggregations
    COALESCE(bi.total_bureau_inquiries, 0) AS total_inquiries_pre_loan,
    COALESCE(bi.personal_loan_inquiries, 0) AS unsecured_inquiries_pre_loan,
    
    -- Financial Stress & Capacity Ratios
    ROUND(l.monthly_emi_inr / NULLIF(b.monthly_income_inr, 0), 4) AS installment_to_income_ratio,
    ROUND(l.disbursed_principal_inr / NULLIF(b.monthly_income_inr * 12.0, 0), 4) AS loan_to_annual_income_ratio,
    ROUND((b.total_existing_monthly_emi + l.monthly_emi_inr) / NULLIF(b.monthly_income_inr, 0), 4) AS total_dti_ratio,
    
    -- Risk Cohort Buckets
    CASE
        WHEN b.cibil_score >= 750 THEN 'Tier_1_Prime'
        WHEN b.cibil_score >= 700 THEN 'Tier_2_Near_Prime'
        WHEN b.cibil_score >= 650 THEN 'Tier_3_Subprime'
        ELSE 'Tier_4_Deep_Subprime'
    END AS credit_risk_segment,

    -- Target Variable (Ground Truth for Supervised PD Classification)
    COALESCE(d.is_default_12m, 0) AS target_default_12m,
    COALESCE(d.max_dpd_first_12m, 0) AS max_dpd_observed_12m,
    COALESCE(d.observed_months_on_book, 0) AS observed_mob

FROM fact_loan_originations l
JOIN dim_borrowers b ON l.borrower_id = b.borrower_id
JOIN dim_loan_products p ON l.product_id = p.product_id
LEFT JOIN first_12m_delinquency d ON l.loan_id = d.loan_id
LEFT JOIN bureau_inquiries_agg bi ON b.borrower_id = bi.borrower_id;
