-- ============================================================================
-- CreditPulse: Vintage Cohort Analysis & Maturation Curves (Cumulative Default %)
-- Dialect: ANSI SQL / Compatible with SQLite, PostgreSQL, DuckDB
-- ============================================================================
-- Business Objective:
-- Track credit underwriting quality across Origination Quarters (Vintages)
-- by measuring cumulative 30+ DPD and 90+ DPD (NPA) default rates at each
-- Month on Book (MOB 1, MOB 2, ... MOB 18).
-- Crucial for Chief Risk Officers (CRO) to detect credit quality decay over time.
-- ============================================================================

WITH loan_vintages AS (
    -- Step 1: Assign each loan to its origination quarter cohort
    SELECT 
        l.loan_id,
        STRFTIME('%Y', l.origination_date) || '-Q' || 
            CAST(((CAST(STRFTIME('%m', l.origination_date) AS INT) - 1) / 3) + 1 AS TEXT) AS origination_vintage,
        l.product_id,
        l.disbursed_principal_inr
    FROM fact_loan_originations l
),

repayment_mobs AS (
    -- Step 2: Extract delinquency status at each Month on Book (installment_number = MOB)
    SELECT 
        r.loan_id,
        r.installment_number AS mob,
        r.dpd_days,
        CASE WHEN r.dpd_days >= 30 THEN 1 ELSE 0 END AS is_30plus_dpd,
        CASE WHEN r.dpd_days >= 90 THEN 1 ELSE 0 END AS is_90plus_dpd
    FROM fact_repayment_schedule r
),

vintage_mob_aggregates AS (
    -- Step 3: Combine vintages with MOB performance
    SELECT 
        v.origination_vintage,
        r.mob,
        COUNT(DISTINCT v.loan_id) AS active_loans_in_mob,
        SUM(v.disbursed_principal_inr) AS active_vintage_volume_inr,
        SUM(r.is_30plus_dpd) AS loans_30plus_dpd_count,
        SUM(r.is_90plus_dpd) AS loans_90plus_dpd_count
    FROM loan_vintages v
    INNER JOIN repayment_mobs r ON v.loan_id = r.loan_id
    GROUP BY v.origination_vintage, r.mob
),

vintage_totals AS (
    -- Step 4: Base total originated volume and count per vintage
    SELECT 
        origination_vintage,
        COUNT(DISTINCT loan_id) AS total_vintage_originated_loans,
        SUM(disbursed_principal_inr) AS total_vintage_disbursed_inr
    FROM loan_vintages
    GROUP BY origination_vintage
)

-- Step 5: Final Vintage Maturation Table
SELECT 
    vma.origination_vintage,
    vt.total_vintage_originated_loans,
    ROUND(vt.total_vintage_disbursed_inr / 100000.0, 2) AS vintage_disbursed_lakhs_inr,
    vma.mob AS month_on_book,
    vma.loans_30plus_dpd_count,
    vma.loans_90plus_dpd_count,
    ROUND((vma.loans_30plus_dpd_count * 100.0) / vt.total_vintage_originated_loans, 2) AS cum_30plus_dpd_rate_pct,
    ROUND((vma.loans_90plus_dpd_count * 100.0) / vt.total_vintage_originated_loans, 2) AS cum_90plus_npa_rate_pct
FROM vintage_mob_aggregates vma
INNER JOIN vintage_totals vt ON vma.origination_vintage = vt.origination_vintage
WHERE vma.mob <= 18
ORDER BY vma.origination_vintage ASC, vma.mob ASC;
