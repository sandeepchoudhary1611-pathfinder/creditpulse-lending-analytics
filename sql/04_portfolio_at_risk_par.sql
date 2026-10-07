-- ==============================================================================
-- CREDITPULSE LENDING ANALYTICS
-- Script: 04_portfolio_at_risk_par.sql
-- Description: Portfolio Health, PAR (30/60/90 DPD), GNPA %, Collections Efficiency,
-- and Provision Coverage Ratio (PCR) analytics across monthly snapshot dates.
-- ==============================================================================

WITH monthly_portfolio_snapshot AS (
    SELECT
        repayment_month AS snapshot_month,
        COUNT(DISTINCT loan_id) AS total_active_loans,
        SUM(closing_balance_inr) AS total_aum_inr,
        SUM(scheduled_emi_amount) AS total_scheduled_demand_inr,
        SUM(paid_amount) AS total_collected_amount_inr,
        
        -- Portfolio at Risk (PAR) Balances
        SUM(CASE WHEN dpd_days > 30 THEN closing_balance_inr ELSE 0 END) AS par_30_balance_inr,
        SUM(CASE WHEN dpd_days > 60 THEN closing_balance_inr ELSE 0 END) AS par_60_balance_inr,
        SUM(CASE WHEN dpd_days > 90 THEN closing_balance_inr ELSE 0 END) AS par_90_gnpa_balance_inr,
        
        -- Loan Counts by DPD Bracket
        COUNT(DISTINCT CASE WHEN dpd_days = 0 THEN loan_id END) AS current_loans,
        COUNT(DISTINCT CASE WHEN dpd_days BETWEEN 1 AND 30 THEN loan_id END) AS dpd_1_30_loans,
        COUNT(DISTINCT CASE WHEN dpd_days BETWEEN 31 AND 60 THEN loan_id END) AS dpd_31_60_loans,
        COUNT(DISTINCT CASE WHEN dpd_days BETWEEN 61 AND 90 THEN loan_id END) AS dpd_61_90_loans,
        COUNT(DISTINCT CASE WHEN dpd_days > 90 THEN loan_id END) AS npa_loans
    FROM fact_repayment_schedule
    GROUP BY repayment_month
)

SELECT
    snapshot_month,
    total_active_loans,
    ROUND(total_aum_inr, 2) AS total_aum_inr,
    
    -- Collections Efficiency %
    ROUND(total_collected_amount_inr * 100.0 / NULLIF(total_scheduled_demand_inr, 0), 2) AS collections_efficiency_pct,
    
    -- Portfolio at Risk (PAR) metrics
    ROUND(par_30_balance_inr, 2) AS par_30_balance_inr,
    ROUND(par_30_balance_inr * 100.0 / NULLIF(total_aum_inr, 0), 2) AS par_30_ratio_pct,
    
    ROUND(par_60_balance_inr, 2) AS par_60_balance_inr,
    ROUND(par_60_balance_inr * 100.0 / NULLIF(total_aum_inr, 0), 2) AS par_60_ratio_pct,
    
    -- Gross NPA (PAR 90) %
    ROUND(par_90_gnpa_balance_inr, 2) AS gnpa_balance_inr,
    ROUND(par_90_gnpa_balance_inr * 100.0 / NULLIF(total_aum_inr, 0), 2) AS gnpa_ratio_pct,
    
    -- Regulatory Expected Credit Loss (ECL) Provisioning (Assuming 70% Provision Coverage Ratio on NPA)
    ROUND(par_90_gnpa_balance_inr * 0.70, 2) AS required_ecl_provision_inr,
    ROUND(
        (par_90_gnpa_balance_inr - (par_90_gnpa_balance_inr * 0.70)) * 100.0 / NULLIF(total_aum_inr, 0),
        2
    ) AS net_npa_ratio_pct,

    -- Loan Distribution
    current_loans,
    dpd_1_30_loans,
    dpd_31_60_loans,
    dpd_61_90_loans,
    npa_loans
FROM monthly_portfolio_snapshot
ORDER BY snapshot_month ASC;
