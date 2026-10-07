"""
CreditPulse Lending Analytics Platform
Data Generator: Synthesizes enterprise-scale retail loan tape, credit bureau profiles,
and delinquency migration history matching FinTech risk standards (Navi, CRED, Bajaj).
Author: Sandeep Choudhary (IIT Delhi)
"""

import os
import sys
import math
import random
import sqlite3
import csv
from datetime import datetime, date, timedelta

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Set deterministic seed
random.seed(42)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
DB_PATH = os.path.join(BASE_DIR, "data", "creditpulse.db")
SQL_DIR = os.path.join(BASE_DIR, "sql")

os.makedirs(RAW_DATA_DIR, exist_ok=True)

NUM_BORROWERS = 50000
NUM_LOANS = 60000

PRODUCTS = [
    {
        "product_id": "PL-UNSEC",
        "product_name": "Digital Personal Loan",
        "product_category": "Personal Loan",
        "secured_flag": 0,
        "min_amount": 30000,
        "max_amount": 500000,
        "default_tenor": 24,
        "base_interest_rate": 15.5,
        "min_cibil": 650
    },
    {
        "product_id": "BNPL-CD",
        "product_name": "Consumer Durable BNPL",
        "product_category": "Buy Now Pay Later",
        "secured_flag": 0,
        "min_amount": 10000,
        "max_amount": 80000,
        "default_tenor": 6,
        "base_interest_rate": 13.0,
        "min_cibil": 620
    },
    {
        "product_id": "AUTO-2W",
        "product_name": "Two-Wheeler EV Loan",
        "product_category": "Vehicle Loan",
        "secured_flag": 1,
        "min_amount": 40000,
        "max_amount": 160000,
        "default_tenor": 24,
        "base_interest_rate": 11.5,
        "min_cibil": 600
    },
    {
        "product_id": "SME-WC",
        "product_name": "Merchant Working Capital",
        "product_category": "Business Loan",
        "secured_flag": 0,
        "min_amount": 100000,
        "max_amount": 1000000,
        "default_tenor": 12,
        "base_interest_rate": 18.0,
        "min_cibil": 680
    },
    {
        "product_id": "LAP-MICRO",
        "product_name": "Micro Loan Against Property",
        "product_category": "Mortgage",
        "secured_flag": 1,
        "min_amount": 300000,
        "max_amount": 1500000,
        "default_tenor": 36,
        "base_interest_rate": 10.2,
        "min_cibil": 650
    }
]

CITY_STATE_MAP = [
    ("Mumbai", "Tier 1", "Maharashtra"),
    ("Bengaluru", "Tier 1", "Karnataka"),
    ("Delhi-NCR", "Tier 1", "Delhi"),
    ("Hyderabad", "Tier 1", "Telangana"),
    ("Pune", "Tier 1", "Maharashtra"),
    ("Chennai", "Tier 1", "Tamil Nadu"),
    ("Jaipur", "Tier 2", "Rajasthan"),
    ("Ahmedabad", "Tier 2", "Gujarat"),
    ("Chandigarh", "Tier 2", "Punjab"),
    ("Lucknow", "Tier 2", "Uttar Pradesh"),
    ("Kochi", "Tier 2", "Kerala"),
    ("Indore", "Tier 2", "Madhya Pradesh"),
    ("Patna", "Tier 3", "Bihar"),
    ("Ranchi", "Tier 3", "Jharkhand"),
    ("Bhopal", "Tier 3", "Madhya Pradesh"),
    ("Bhubaneswar", "Tier 3", "Odisha"),
    ("Nagpur", "Tier 3", "Maharashtra"),
    ("Varanasi", "Tier 3", "Uttar Pradesh")
]

def calculate_emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    r = (annual_rate / 100.0) / 12.0
    if r == 0:
        return principal / tenure_months
    emi = principal * r * ((1 + r) ** tenure_months) / (((1 + r) ** tenure_months) - 1)
    return round(emi, 2)

def generate_data():
    print("=" * 70)
    print(">>> CreditPulse: Generating Enterprise Lending Portfolio Data...")
    print("=" * 70)

    # 1. Borrowers (dim_borrowers)
    print(f"[*] Synthesizing {NUM_BORROWERS:,} borrower profiles...")
    borrowers = []
    emp_types = [
        ("Salaried - Corporate", 0.45),
        ("Salaried - SME", 0.25),
        ("Self-Employed - Professional", 0.12),
        ("Self-Employed - Business", 0.10),
        ("Gig Economy / Contractual", 0.08)
    ]
    emp_choices = [x[0] for x in emp_types]
    emp_weights = [x[1] for x in emp_types]

    for i in range(1, NUM_BORROWERS + 1):
        b_id = f"BW-{i:06d}"
        age = int(random.triangular(21, 62, 31))
        gender = random.choices(["M", "F", "Other"], weights=[0.63, 0.36, 0.01])[0]
        emp = random.choices(emp_choices, weights=emp_weights)[0]
        
        # Monthly income: log-normal with median ~44,000 INR
        base_log_income = random.gauss(10.7, 0.52)
        monthly_income = int(round(math.exp(base_log_income) / 500.0) * 500)
        monthly_income = max(18000, min(monthly_income, 450000))
        
        # Geography
        city_info = random.choices(
            CITY_STATE_MAP,
            weights=[12, 11, 12, 9, 8, 8, 5, 5, 4, 4, 3, 3, 3, 2, 3, 2, 3, 3]
        )[0]
        city, city_tier, state = city_info
        
        residence = random.choices(["Rented", "Owned", "Family Owned"], weights=[0.52, 0.32, 0.16])[0]
        
        # CIBIL Score (mean ~715, std ~58)
        cibil = int(round(random.gauss(715, 58)))
        cibil = max(550, min(cibil, 850))
        
        if cibil < 650:
            total_accounts = random.randint(3, 10)
            active_loans = random.randint(2, 6)
            utilization = round(random.uniform(0.65, 0.98), 4)
            hist_dpd = random.choices([0, 15, 30, 60, 90], weights=[0.20, 0.30, 0.25, 0.15, 0.10])[0]
            inq_30d = random.choices([0, 1, 2, 3, 4], weights=[0.2, 0.3, 0.25, 0.15, 0.1])[0]
            dti = round(random.uniform(0.40, 0.75), 4)
        elif cibil < 720:
            total_accounts = random.randint(2, 7)
            active_loans = random.randint(1, 4)
            utilization = round(random.uniform(0.35, 0.70), 4)
            hist_dpd = random.choices([0, 15, 30, 45], weights=[0.65, 0.20, 0.10, 0.05])[0]
            inq_30d = random.choices([0, 1, 2, 3], weights=[0.5, 0.3, 0.15, 0.05])[0]
            dti = round(random.uniform(0.25, 0.50), 4)
        else: # Prime >= 720
            total_accounts = random.randint(1, 6)
            active_loans = random.randint(0, 3)
            utilization = round(random.uniform(0.05, 0.40), 4)
            hist_dpd = random.choices([0, 10], weights=[0.92, 0.08])[0]
            inq_30d = random.choices([0, 1, 2], weights=[0.8, 0.15, 0.05])[0]
            dti = round(random.uniform(0.10, 0.35), 4)
            
        inq_90d = inq_30d + random.choices([0, 1, 2, 3], weights=[0.5, 0.3, 0.15, 0.05])[0]
        existing_emi = round(monthly_income * dti, 2)
        created_at = "2023-12-01"
        
        borrowers.append((
            b_id, age, gender, emp, monthly_income, cibil, city, city_tier, state,
            residence, total_accounts, active_loans, existing_emi, dti, utilization,
            inq_30d, inq_90d, hist_dpd, created_at
        ))

    # 2. Products (dim_loan_products)
    print("[*] Setting up loan product definitions...")
    product_rows = [
        (p["product_id"], p["product_name"], p["product_category"], p["secured_flag"],
         p["base_interest_rate"], p["default_tenor"], p["min_cibil"])
        for p in PRODUCTS
    ]

    # 3. Bureau Inquiries (fact_bureau_inquiries)
    print("[*] Generating bureau inquiry histories...")
    inquiries = []
    inq_id_counter = 1
    lender_types = ["FinTech NBFC", "Private Bank", "PSU Bank", "Digital Lending App"]
    inquiry_purposes = ["Unsecured Personal Loan", "Credit Card", "BNPL", "Vehicle Loan", "Business Loan"]

    for b in borrowers:
        b_id = b[0]
        n_inq = b[15] + b[16] # inq_30d + inq_90d
        for _ in range(n_inq):
            iq_id = f"INQ-{inq_id_counter:07d}"
            inq_id_counter += 1
            days_ago = random.randint(1, 120)
            inq_date = (date(2025, 12, 1) - timedelta(days=days_ago)).isoformat()
            purp = random.choice(inquiry_purposes)
            lender = random.choice(lender_types)
            amt_req = random.choice([25000, 50000, 100000, 200000, 500000])
            inquiries.append((iq_id, b_id, inq_date, purp, lender, amt_req))

    # 4. Originations & Repayment Schedule Simulation
    print(f"[*] Originating {NUM_LOANS:,} loans & simulating monthly payment tapes...")
    loans = []
    repayment_rows = []
    
    purposes = ["Debt Consolidation", "Medical Emergency", "Home Renovation", "Gadget / Lifestyle", "Wedding / Travel", "Business Expansion", "Education"]
    start_date = date(2024, 1, 1)
    end_date = date(2025, 11, 15)
    study_cutoff = date(2025, 12, 31)
    days_range = (end_date - start_date).days

    borrower_lookup = {b[0]: b for b in borrowers}
    all_borrower_ids = list(borrower_lookup.keys())

    rep_id_counter = 1

    for i in range(1, NUM_LOANS + 1):
        l_id = f"LN-{i:07d}"
        b_id = random.choice(all_borrower_ids)
        b_prof = borrower_lookup[b_id]
        b_income = b_prof[4]
        b_cibil = b_prof[5]
        
        prod = random.choices(PRODUCTS, weights=[0.42, 0.25, 0.15, 0.12, 0.06])[0]
        
        # Loan ticket amount
        max_possible = min(prod["max_amount"], b_income * 8)
        min_possible = min(prod["min_amount"], max_possible)
        amt = round(random.triangular(min_possible, max_possible, (min_possible + max_possible) * 0.4) / 5000.0) * 5000
        amt = max(prod["min_amount"], amt)
        
        tenure = random.choice([3, 6, 12, 18, 24, 36, 48, 60])
        if prod["product_category"] == "Buy Now Pay Later":
            tenure = random.choice([3, 6, 12])
        elif prod["product_category"] == "Mortgage":
            tenure = random.choice([24, 36, 48, 60])
        else:
            tenure = random.choice([12, 18, 24, 36])
            
        rate = prod["base_interest_rate"]
        if b_cibil < 650:
            rate += random.uniform(4.5, 7.5)
        elif b_cibil < 720:
            rate += random.uniform(1.5, 3.5)
        else:
            rate -= random.uniform(0.5, 2.0)
        rate = round(max(8.5, min(rate, 28.0)), 2)
        
        emi = calculate_emi(amt, rate, tenure)
        total_receivable = round(emi * tenure, 2)
        purpose = random.choice(purposes)
        
        orig_days = random.randint(0, days_range)
        orig_dt = start_date + timedelta(days=orig_days)
        orig_date_str = orig_dt.isoformat()
        
        # Intrinsic risk latent factor
        dti = emi / max(1.0, float(b_income))
        latent_z = (
            -1.1
            - ((b_cibil - 700.0) / 45.0)
            + (dti * 3.8)
            + (0.7 if prod["secured_flag"] == 0 else -0.6)
            + ((rate - 15.0) / 7.0)
        )
        base_pd = 1.0 / (1.0 + math.exp(-latent_z))
        base_pd = max(0.015, min(base_pd, 0.45))
        
        # Simulate monthly tape
        balance = float(amt)
        monthly_rate = (rate / 100.0) / 12.0
        current_dpd = 0
        is_written_off = False
        default_date_str = None
        has_defaulted = 0
        total_prin_paid = 0.0
        total_int_paid = 0.0
        
        for mob in range(1, tenure + 1):
            month_offset = orig_dt.month + mob
            year_offset = orig_dt.year + (month_offset - 1) // 12
            month_norm = ((month_offset - 1) % 12) + 1
            due_dt = date(year_offset, month_norm, min(orig_dt.day, 28))
            
            if due_dt > study_cutoff:
                break
                
            interest_comp = round(balance * monthly_rate, 2)
            principal_comp = round(min(balance, emi - interest_comp), 2)
            if principal_comp < 0:
                principal_comp = 0.0
                
            opening_bal = balance
            
            # Markov Delinquency State Machine
            if is_written_off:
                current_dpd = min(180, current_dpd + 30)
                paid_amt = 0.0
                closing_bal = opening_bal
                bucket = "4_DPD_90_Plus"
                inst_status = "Written_Off"
            else:
                if current_dpd == 0:
                    miss_prob = base_pd * 0.35
                    if random.random() < miss_prob:
                        current_dpd = random.randint(5, 28)
                        paid_amt = round(random.choice([0.0, emi * 0.5]), 2)
                    else:
                        current_dpd = 0
                        paid_amt = emi
                elif current_dpd <= 30:
                    cure_prob = 0.68 - (base_pd * 0.35)
                    if random.random() < cure_prob:
                        current_dpd = 0
                        paid_amt = round(emi * 1.5, 2)
                    else:
                        current_dpd = random.randint(35, 58)
                        paid_amt = 0.0
                elif current_dpd <= 60:
                    cure_prob = 0.32 - (base_pd * 0.3)
                    if random.random() < cure_prob:
                        current_dpd = random.randint(0, 15)
                        paid_amt = emi
                    else:
                        current_dpd = random.randint(65, 88)
                        paid_amt = 0.0
                elif current_dpd <= 90:
                    cure_prob = 0.12
                    if random.random() < cure_prob:
                        current_dpd = 30
                        paid_amt = emi
                    else:
                        current_dpd = random.randint(95, 120)
                        paid_amt = 0.0
                else: # 90+ DPD
                    current_dpd = min(180, current_dpd + 30)
                    paid_amt = 0.0
                    if current_dpd >= 150:
                        is_written_off = True
                        
                # Accounting balances
                actual_int = min(paid_amt, interest_comp)
                actual_prin = min(balance, max(0.0, paid_amt - actual_int))
                closing_bal = round(max(0.0, opening_bal - actual_prin), 2)
                balance = closing_bal
                
                total_prin_paid = round(total_prin_paid + actual_prin, 2)
                total_int_paid = round(total_int_paid + actual_int, 2)
                
                if current_dpd == 0:
                    bucket = "0_Current"
                    inst_status = "Paid_On_Time"
                    pay_date_str = due_dt.isoformat()
                elif current_dpd <= 30:
                    bucket = "1_DPD_1_30"
                    inst_status = "Paid_Late" if paid_amt > 0 else "Missed_Delinquent"
                    pay_date_str = (due_dt + timedelta(days=current_dpd)).isoformat() if paid_amt > 0 else None
                elif current_dpd <= 60:
                    bucket = "2_DPD_31_60"
                    inst_status = "Missed_Delinquent"
                    pay_date_str = None
                elif current_dpd <= 90:
                    bucket = "3_DPD_61_90"
                    inst_status = "Missed_Delinquent"
                    pay_date_str = None
                else:
                    bucket = "4_DPD_90_Plus"
                    inst_status = "Missed_Delinquent"
                    pay_date_str = None
                    if has_defaulted == 0:
                        has_defaulted = 1
                        default_date_str = due_dt.isoformat()

            rep_id = f"RP-{rep_id_counter:08d}"
            rep_id_counter += 1
            repay_month_str = due_dt.strftime("%Y-%m")
            
            repayment_rows.append((
                rep_id, l_id, mob, due_dt.isoformat(), repay_month_str,
                pay_date_str, emi, paid_amt, principal_comp, interest_comp,
                closing_bal, current_dpd, bucket, inst_status
            ))
            
            if closing_bal == 0.0 and current_dpd == 0:
                break # Loan fully paid off

        # Loan final snapshot
        if is_written_off:
            final_status = "Defaulted / Written-Off"
            final_bucket = "4_DPD_90_Plus"
            final_is_def = 1
        elif current_dpd >= 90:
            final_status = "Defaulted / Written-Off"
            final_bucket = "4_DPD_90_Plus"
            final_is_def = 1
        elif balance == 0.0:
            final_status = "Fully Paid"
            final_bucket = "0_Current"
            final_is_def = has_defaulted
        else:
            final_status = "Active"
            final_is_def = has_defaulted
            if current_dpd == 0:
                final_bucket = "0_Current"
            elif current_dpd <= 30:
                final_bucket = "1_DPD_1_30"
            elif current_dpd <= 60:
                final_bucket = "2_DPD_31_60"
            else:
                final_bucket = "3_DPD_61_90"

        loans.append((
            l_id, b_id, prod["product_id"], orig_date_str, amt, rate, tenure,
            emi, total_receivable, final_status, current_dpd, final_bucket,
            final_is_def, default_date_str, total_prin_paid, total_int_paid,
            balance, purpose
        ))

    print(f"[+] Total monthly installment ledger rows: {len(repayment_rows):,}")

    # Write Raw CSVs
    print("[*] Writing raw CSVs to data/raw/...")
    
    with open(os.path.join(RAW_DATA_DIR, "dim_borrowers.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "borrower_id", "age", "gender", "employment_type", "monthly_income_inr",
            "cibil_score", "city", "city_tier", "state", "residence_ownership",
            "bureau_total_accounts", "bureau_active_loans_count", "total_existing_monthly_emi",
            "debt_to_income_ratio", "credit_utilization_ratio", "bureau_inquiries_last_30d",
            "bureau_inquiries_last_90d", "historical_dpd_max_last_12m", "created_at"
        ])
        writer.writerows(borrowers)

    with open(os.path.join(RAW_DATA_DIR, "dim_loan_products.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "product_id", "product_name", "product_category", "secured_flag",
            "annual_interest_rate_pct", "default_tenor_months", "min_cibil_threshold"
        ])
        writer.writerows(product_rows)

    with open(os.path.join(RAW_DATA_DIR, "fact_bureau_inquiries.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["inquiry_id", "borrower_id", "inquiry_date", "inquiry_purpose", "inquiry_lender_type", "amount_requested"])
        writer.writerows(inquiries)

    with open(os.path.join(RAW_DATA_DIR, "fact_loan_originations.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "loan_id", "borrower_id", "product_id", "origination_date", "disbursed_principal_inr",
            "annual_interest_rate", "tenor_months", "monthly_emi_inr", "total_receivable_inr",
            "loan_status", "current_dpd", "current_delinquency_bucket", "is_default_flag",
            "default_date", "total_principal_paid", "total_interest_paid", "outstanding_balance_inr",
            "loan_purpose"
        ])
        writer.writerows(loans)

    with open(os.path.join(RAW_DATA_DIR, "fact_repayment_schedule.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "schedule_id", "loan_id", "installment_number", "due_date", "repayment_month",
            "payment_date", "scheduled_emi_amount", "paid_amount", "principal_component",
            "interest_component", "closing_balance_inr", "dpd_days", "delinquency_bucket",
            "installment_status"
        ])
        writer.writerows(repayment_rows)

    print("[OK] Raw CSVs dumped successfully.")

    # Populate Relational SQLite DB
    print(f"[*] Initializing SQLite database schema at {DB_PATH}...")
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    with open(os.path.join(SQL_DIR, "01_schema_setup.sql"), "r", encoding="utf-8") as f:
        schema_sql = f.read()
    cursor.executescript(schema_sql)
    conn.commit()

    print("[*] Inserting records into database with bulk transaction...")
    cursor.executemany("INSERT INTO dim_borrowers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", borrowers)
    cursor.executemany("INSERT INTO dim_loan_products VALUES (?, ?, ?, ?, ?, ?, ?)", product_rows)
    cursor.executemany("INSERT INTO fact_bureau_inquiries VALUES (?, ?, ?, ?, ?, ?)", inquiries)
    
    # Loans mapping
    loan_db_rows = [
        (l[0], l[1], l[2], l[3], l[4], l[5], l[6], l[7], l[8], l[17], l[9], l[10], l[11], l[12], l[13], l[14], l[15], l[16])
        for l in loans
    ]
    cursor.executemany("""
        INSERT INTO fact_loan_originations (
            loan_id, borrower_id, product_id, origination_date, disbursed_principal_inr,
            annual_interest_rate, tenor_months, monthly_emi_inr, total_receivable_inr,
            loan_purpose, loan_status, current_dpd, current_delinquency_bucket,
            is_default_flag, default_date, total_principal_paid, total_interest_paid,
            outstanding_balance_inr
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, loan_db_rows)

    cursor.executemany("""
        INSERT INTO fact_repayment_schedule VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, repayment_rows)
    
    conn.commit()

    # Create analytical view
    print("[*] Compiling view_underwriting_ml_features view...")
    with open(os.path.join(SQL_DIR, "05_underwriting_ml_feature_view.sql"), "r", encoding="utf-8") as f:
        view_sql = f.read()
    cursor.executescript(view_sql)
    conn.commit()

    # Verify counts
    print("-" * 70)
    print(">>> Database Table Verification Summary:")
    for tbl in ["dim_borrowers", "dim_loan_products", "fact_loan_originations", "fact_bureau_inquiries", "fact_repayment_schedule"]:
        cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
        cnt = cursor.fetchone()[0]
        print(f"    - {tbl:<28}: {cnt:>10,} rows")

    cursor.execute("SELECT COUNT(*), SUM(target_default_12m) FROM view_underwriting_ml_features")
    ml_tot, ml_def = cursor.fetchone()
    print(f"    - {'view_underwriting_ml_features':<28}: {ml_tot:>10,} loans (Defaults: {ml_def:,} -> {ml_def*100.0/ml_tot:.2f}% default rate)")
    print("-" * 70)

    conn.close()
    print("[OK] CreditPulse Data Generation & Warehousing Completed Successfully.")

if __name__ == "__main__":
    generate_data()
