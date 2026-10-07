# CreditPulse: Power BI Dashboard Architecture & UI/UX Specifications

## 1. Executive Summary & Canvas Standards
The **CreditPulse Lending Analytics Dashboard** is structured into a 4-page, publication-grade executive analytics suite tailored for Chief Risk Officers (CRO), Credit Committees, and Portfolio Risk Analytics teams in consumer FinTech NBFCs (Navi, CRED, Bajaj Finance, OneCard, Capital One).

### Canvas Standard
- **Resolution:** 16:9 Standard (1920 x 1080 px)
- **Theme Palette:**
  - **Background:** `#0B132B` (Deep FinTech Navy)
  - **Card Containers:** `#1C2541` (Slate Blue)
  - **Primary Brand / Approvals:** `#00D2D3` (Electric Cyan) & `#10AC84` (Emerald Green)
  - **Risk / NPA / Default:** `#EE5253` (Crimson Red)
  - **Watchlist / PAR Warnings:** `#FF9F43` (Amber Orange)
  - **Text Typography:** Segoe UI / Din Condensed (Financial Grade)

---

## 2. Page-by-Page Structural Layout

### Page 1: CRO Executive Risk & Portfolio Cockpit
**Target Audience:** Chief Risk Officer, Head of Credit, CEO.
- **Top Header KPI Strip (Cards):**
  - Card 1: `Total Active AUM (INR Cr)` (e.g., INR 784.2 Cr)
  - Card 2: `Gross NPA % (PAR-90)` with Target Threshold (< 2.50%)
  - Card 3: `PAR-30 %` with MoM Delta indicator
  - Card 4: `Collections Efficiency %` (Target > 98.0%)
  - Card 5: `Expected Credit Loss (ECL) Provision (INR Cr)`
- **Visual 1 (Area / Clustered Column Chart):**
  - Disbursal Volume & Active AUM Growth by Month (Jan 2024 - Dec 2025).
- **Visual 2 (100% Stacked Bar Chart):**
  - Portfolio Quality Breakdown by Delinquency Bucket (`Current`, `1-30 DPD`, `31-60 DPD`, `61-90 DPD`, `90+ DPD`).
- **Visual 3 (Donut Chart):**
  - Product Category Mix (`Unsecured Personal Loan`, `BNPL`, `Two-Wheeler`, `MSME Working Capital`, `Micro LAP`).
- **Visual 4 (Scatter Plot):**
  - Risk vs. Return Matrix: Average APR (%) vs. GNPA (%) across City Tiers and Employment Types.

---

### Page 2: Vintage Maturation & Cohort Decay Curves
**Target Audience:** Quantitative Credit Risk Modelers, Underwriting Policy Heads.
- **Top Filter Slicers:**
  - Product Category Slicer (Multi-select)
  - Origination Vintage Quarter (`2024-Q1` through `2025-Q3`)
  - Ticket Size Band (`<50k`, `50k-2L`, `2L-5L`, `>5L`)
- **Visual 1 (Multi-line Maturation Curve):**
  - **X-axis:** Months on Book (MOB 1 to 18)
  - **Y-axis:** Cumulative 30+ DPD %
  - **Legend:** Origination Vintage Cohort (Color-coded lines).
  - *Strategic Insight:* Identifies underwriting policy loosening in recent quarters before loans reach terminal default.
- **Visual 2 (Multi-line Maturation Curve):**
  - **X-axis:** Months on Book (MOB 1 to 18)
  - **Y-axis:** Cumulative 90+ DPD (NPA) %
  - **Legend:** Origination Vintage Cohort.
- **Visual 3 (Matrix Grid):**
  - Vintage Cohort x MOB Heatmap Table with conditional color scales (Green -> Yellow -> Red).

---

### Page 3: Delinquency Migration & Roll-Rate Matrix
**Target Audience:** Collections Strategy Heads, Recovery Operations, Credit Operations.
- **Visual 1 (Heatmap Matrix - Markov Transition State):**
  - **Rows:** Starting Delinquency Bucket Month $T$ (`0_Current`, `1_DPD_1_30`, `2_DPD_31_60`, `3_DPD_61_90`)
  - **Columns:** Ending Delinquency Bucket Month $T+1$ (`0_Current`, `1_DPD_1_30`, `2_DPD_31_60`, `3_DPD_61_90`, `4_DPD_90_Plus`)
  - **Values:** Volume Roll-Rate % (`volume_roll_rate_pct`)
  - *Color Scale:* High Cure % (Green), High Roll-Forward % (Deep Red).
- **Visual 2 (Gauge Charts):**
  - Current Cure Rate (1-30 DPD -> Current): Target 70% | Actual 68.2%
  - Roll-Forward Rate (61-90 DPD -> Default): Actual 88.4%
- **Visual 3 (Decomposition Tree):**
  - Root: Total Delinquent Volume (>0 DPD) -> Product -> Employment Type -> Bureau Inquiries -> City Tier.

---

### Page 4: ML Credit Underwriting & GenAI Referral Copilot
**Target Audience:** Credit Underwriting Managers, Credit Committee, Risk Data Scientists.
- **Top KPI Cards:**
  - Model ROC-AUC (`0.717`) | Gini (`0.433`) | KS-Statistic (`36.4%`)
  - Auto-Approval Rate (`58.4%`)
  - Referral Triage Rate (`18.2%`)
  - Auto-Decline Rate (`23.4%`)
- **Visual 1 (Dual Density / Area Plot):**
  - Internal CreditPulse Score Distribution: Separation between Good Loans vs. Defaulted Loans.
- **Visual 2 (Bar Chart - Feature Weights):**
  - Top 10 Underwriting Drivers: `CIBIL Score`, `Estimated DTI`, `Historical DPD Max`, `Credit Utilization`, `Inquiries 30d`.
- **Visual 3 (Interactive Referral Triage Table & LLM Memo View):**
  - Grid showing Borderline Applications (`loan_id`, `borrower_id`, `cibil_score`, `total_dti_ratio`, `predicted_pd`, `underwriting_decision`).
  - Drill-through / Tooltip Card displaying the **AI Underwriting Exception Memo**:
    - Recommended Sanction Amount
    - Compensating Strengths
    - Risk Flags & Prescribed Policy Covenants.

---

## 3. Data Model Relationships (Star Schema)

```
        +-------------------------+
        |      dim_borrowers      |
        +-------------------------+
                     | 1
                     |
                     | *
+------------------------------------+       * +--------------------------+
|      fact_loan_originations        |---------|    dim_loan_products     |
+------------------------------------+         +--------------------------+
  | 1                   | 1
  |                     |
  | *                   | 1
+--------------------+ +----------------------------------------+
|fact_repayment_     | | fact_loan_underwriting_scores          |
|schedule            | +----------------------------------------+
+--------------------+
```

All relationships are 1-to-many, single-directional cross filtering to optimize DAX memory cache and VertiPaq engine compression.
