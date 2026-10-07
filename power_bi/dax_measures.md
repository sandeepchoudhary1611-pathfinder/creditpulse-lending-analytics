# CreditPulse: Production DAX Measures & Financial Formulas

This document contains enterprise-grade **DAX (Data Analysis Expressions)** measures designed for the **CreditPulse Power BI Executive Risk & Portfolio Intelligence Dashboard**.

---

## 1. Portfolio Health & AUM Measures

### Total Active AUM (Assets Under Management)
```dax
Total Active AUM = 
CALCULATE(
    SUM(fact_repayment_schedule[closing_balance_inr]),
    LASTNONBLANK(fact_repayment_schedule[repayment_month], 1)
)
```

### Total Disbursed Volume
```dax
Total Disbursed Volume = 
SUM(fact_loan_originations[disbursed_principal_inr])
```

### Total Active Loan Count
```dax
Active Loan Count = 
CALCULATE(
    DISTINCTCOUNT(fact_repayment_schedule[loan_id]),
    fact_repayment_schedule[closing_balance_inr] > 0
)
```

### Average Ticket Size (ATS)
```dax
Average Ticket Size = 
DIVIDE(
    [Total Disbursed Volume],
    DISTINCTCOUNT(fact_loan_originations[loan_id]),
    0
)
```

### Weighted Average Portfolio APR (%)
```dax
Weighted Average APR = 
DIVIDE(
    SUMX(fact_loan_originations, fact_loan_originations[disbursed_principal_inr] * fact_loan_originations[annual_interest_rate]),
    [Total Disbursed Volume],
    0
)
```

---

## 2. Portfolio at Risk (PAR) & NPA Metrics

### PAR-30 Balance (Exposure > 30 DPD)
```dax
PAR 30 Balance = 
CALCULATE(
    SUM(fact_repayment_schedule[closing_balance_inr]),
    fact_repayment_schedule[dpd_days] > 30
)
```

### PAR-30 Ratio (%)
```dax
PAR 30 Ratio % = 
DIVIDE(
    [PAR 30 Balance],
    [Total Active AUM],
    0
)
```

### Gross Non-Performing Assets (GNPA / PAR-90 Balance)
```dax
GNPA Balance = 
CALCULATE(
    SUM(fact_repayment_schedule[closing_balance_inr]),
    fact_repayment_schedule[dpd_days] >= 90
)
```

### Gross NPA Ratio (%)
```dax
Gross NPA % = 
DIVIDE(
    [GNPA Balance],
    [Total Active AUM],
    0
)
```

### Regulatory ECL Provision (70% PCR Standard)
```dax
ECL Provision Balance = 
[GNPA Balance] * 0.70
```

### Net NPA Ratio (%)
```dax
Net NPA % = 
DIVIDE(
    [GNPA Balance] - [ECL Provision Balance],
    [Total Active AUM] - [ECL Provision Balance],
    0
)
```

---

## 3. Delinquency Roll Rates & Collections Efficiency

### Collections Efficiency Ratio (%)
```dax
Collections Efficiency % = 
DIVIDE(
    SUM(fact_repayment_schedule[paid_amount]),
    SUM(fact_repayment_schedule[scheduled_emi_amount]),
    0
)
```

### Month-over-Month Roll-Forward Rate (1-30 DPD to 31-60 DPD)
```dax
Roll Forward Rate 30 to 60 % = 
VAR RollForwardVolume = 
    CALCULATE(
        SUM(delinquency_roll_rate_matrix[exposure_at_risk_inr]),
        delinquency_roll_rate_matrix[bucket_t0] = "1_DPD_1_30",
        delinquency_roll_rate_matrix[bucket_t1] = "2_DPD_31_60"
    )
VAR StartingBucketVolume = 
    CALCULATE(
        SUM(delinquency_roll_rate_matrix[exposure_at_risk_inr]),
        delinquency_roll_rate_matrix[bucket_t0] = "1_DPD_1_30"
    )
RETURN
    DIVIDE(RollForwardVolume, StartingBucketVolume, 0)
```

### Bucket Cure Rate (1-30 DPD Back to Current)
```dax
Cure Rate 30 to Current % = 
VAR CureVolume = 
    CALCULATE(
        SUM(delinquency_roll_rate_matrix[exposure_at_risk_inr]),
        delinquency_roll_rate_matrix[bucket_t0] = "1_DPD_1_30",
        delinquency_roll_rate_matrix[bucket_t1] = "0_Current"
    )
VAR StartingBucketVolume = 
    CALCULATE(
        SUM(delinquency_roll_rate_matrix[exposure_at_risk_inr]),
        delinquency_roll_rate_matrix[bucket_t0] = "1_DPD_1_30"
    )
RETURN
    DIVIDE(CureVolume, StartingBucketVolume, 0)
```

---

## 4. Vintage Maturation & Cumulative Cohort Curves

### Vintage Cumulative 30+ DPD %
```dax
Cumulative 30+ DPD % = 
DIVIDE(
    CALCULATE(
        DISTINCTCOUNT(fact_repayment_schedule[loan_id]),
        fact_repayment_schedule[dpd_days] >= 30
    ),
    DISTINCTCOUNT(fact_loan_originations[loan_id]),
    0
)
```

### Vintage Cumulative 90+ DPD (NPA) %
```dax
Cumulative 90+ DPD % = 
DIVIDE(
    CALCULATE(
        DISTINCTCOUNT(fact_repayment_schedule[loan_id]),
        fact_repayment_schedule[dpd_days] >= 90
    ),
    DISTINCTCOUNT(fact_loan_originations[loan_id]),
    0
)
```

---

## 5. Underwriting Scorecard & Risk Triage Funnel

### Auto-Approval Rate (%)
```dax
Auto Approval Rate % = 
DIVIDE(
    CALCULATE(COUNTROWS(fact_loan_underwriting_scores), fact_loan_underwriting_scores[underwriting_decision] = "AUTO_APPROVE"),
    COUNTROWS(fact_loan_underwriting_scores),
    0
)
```

### Borderline Referral Triage Rate (%)
```dax
Referral Triage Rate % = 
DIVIDE(
    CALCULATE(COUNTROWS(fact_loan_underwriting_scores), fact_loan_underwriting_scores[underwriting_decision] = "REFERRAL_TRIAGE"),
    COUNTROWS(fact_loan_underwriting_scores),
    0
)
```

### Total Expected Credit Loss (EL)
```dax
Total Expected Credit Loss INR = 
SUM(fact_loan_underwriting_scores[expected_loss_inr])
```

### Portfolio Expected Loss Ratio (% of Total Disbursal)
```dax
Expected Loss Ratio % = 
DIVIDE(
    [Total Expected Credit Loss INR],
    [Total Disbursed Volume],
    0
)
```
