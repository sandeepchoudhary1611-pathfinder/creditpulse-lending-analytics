-- ==============================================================================
-- CREDITPULSE LENDING ANALYTICS
-- Script: 03_delinquency_roll_rates.sql
-- Description: Delinquency Bucket Transition & Markov Roll-Rate Matrix.
-- Tracks month-over-month migration across DPD buckets:
-- 0_Current -> 1_DPD_1_30 -> 2_DPD_31_60 -> 3_DPD_61_90 -> 4_DPD_90_Plus (NPA)
-- Also measures 'Cure Rate' (moving back to Current) and 'Roll Forward Rate'.
-- Leverages (loan_id, installment_number) index for high-speed join.
-- ==============================================================================

WITH monthly_loan_status AS (
    -- Map each loan's performance in month T
    SELECT
        loan_id,
        installment_number,
        repayment_month,
        dpd_days,
        delinquency_bucket AS bucket_state,
        closing_balance_inr
    FROM fact_repayment_schedule
),

transition_pairs AS (
    -- Join month T with month T+1 using installment_number index
    SELECT
        curr.repayment_month AS snapshot_month,
        curr.loan_id,
        curr.bucket_state AS bucket_t0,
        curr.closing_balance_inr AS balance_t0,
        COALESCE(nxt.bucket_state, '5_Settled_or_Matured') AS bucket_t1,
        COALESCE(nxt.closing_balance_inr, 0) AS balance_t1
    FROM monthly_loan_status curr
    LEFT JOIN monthly_loan_status nxt
        ON curr.loan_id = nxt.loan_id
        AND nxt.installment_number = curr.installment_number + 1
),

bucket_transition_summary AS (
    -- Aggregate migration counts and exposure volumes
    SELECT
        snapshot_month,
        bucket_t0,
        bucket_t1,
        COUNT(DISTINCT loan_id) AS loan_count,
        ROUND(SUM(balance_t0), 2) AS exposure_at_risk_inr
    FROM transition_pairs
    WHERE snapshot_month IS NOT NULL
    GROUP BY snapshot_month, bucket_t0, bucket_t1
),

roll_rate_matrix AS (
    -- Calculate transition percentage out of starting bucket t0
    SELECT
        snapshot_month,
        bucket_t0,
        bucket_t1,
        loan_count,
        exposure_at_risk_inr,
        ROUND(
            loan_count * 100.0 / SUM(loan_count) OVER (PARTITION BY snapshot_month, bucket_t0),
            2
        ) AS count_roll_rate_pct,
        ROUND(
            exposure_at_risk_inr * 100.0 / NULLIF(SUM(exposure_at_risk_inr) OVER (PARTITION BY snapshot_month, bucket_t0), 0),
            2
        ) AS volume_roll_rate_pct
    FROM bucket_transition_summary
)

SELECT
    snapshot_month,
    bucket_t0,
    bucket_t1,
    loan_count,
    exposure_at_risk_inr,
    count_roll_rate_pct,
    volume_roll_rate_pct,
    CASE
        WHEN bucket_t0 = '1_DPD_1_30' AND bucket_t1 = '0_Current' THEN 'Cure (Resolved)'
        WHEN bucket_t0 = '1_DPD_1_30' AND bucket_t1 = '2_DPD_31_60' THEN 'Roll-Forward (Worsened)'
        WHEN bucket_t0 = '2_DPD_31_60' AND bucket_t1 = '3_DPD_61_90' THEN 'Roll-Forward (Worsened)'
        WHEN bucket_t0 = '3_DPD_61_90' AND bucket_t1 = '4_DPD_90_Plus' THEN 'Default Impairment'
        WHEN bucket_t0 = bucket_t1 THEN 'Stable (Same Bucket)'
        ELSE 'Other Migration'
    END AS transition_behavior
FROM roll_rate_matrix
ORDER BY snapshot_month DESC, bucket_t0, bucket_t1;
