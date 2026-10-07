"""
CreditPulse Lending Analytics Platform
Master Orchestration Pipeline
Author: Sandeep Choudhary (IIT Delhi)
Description:
    End-to-end execution pipeline for loan tape synthesis, SQLite warehousing,
    dual credit scorecards (Logistic & HistGradientBoosting), Expected Loss (EL),
    AI Underwriting Copilot referral triage, and analytical SQL models.
"""

import os
import sys
import time
import subprocess

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
PYTHON_EXE = sys.executable

def run_step(step_name: str, script_name: str):
    print("\n" + "=" * 80)
    print(f">>> [STEP] {step_name.upper()}")
    print("=" * 80)
    script_path = os.path.join(SRC_DIR, script_name)
    start_time = time.time()
    result = subprocess.run([PYTHON_EXE, script_path], check=True)
    duration = time.time() - start_time
    print(f"[+] Completed '{step_name}' in {duration:.2f} seconds.")

def main():
    print("""
    ========================================================================
    *                      CREDITPULSE LENDING ANALYTICS                   *
    *    Digital Lending Underwriting, Vintage Curves & Delinquency Engine  *
    *                      Author: Sandeep Choudhary (IIT Delhi)           *
    ========================================================================
    """)
    t0 = time.time()

    # Step 1: Data Generation & Relational Warehousing
    run_step("1. Data Warehouse & Loan Tape Synthesis", "generate_lending_data.py")

    # Step 2: Quantitative Credit Scoring & Risk Modeling
    run_step("2. ML Credit Scoring (PD, EAD, LGD & Scorecards)", "credit_scoring_model.py")

    # Step 3: AI Underwriting Copilot & Referral Triage
    run_step("3. AI Underwriting Copilot & Borderline Referral Triage", "ai_underwriting_copilot.py")

    # Step 4: Analytical SQL Models & Portfolio Intelligence
    run_step("4. Analytical SQL Models (Vintages, Roll-Rates & PAR)", "run_sql_analysis.py")

    total_time = time.time() - t0
    print("\n" + "=" * 80)
    print(f"[OK] CreditPulse Pipeline Fully Executed in {total_time:.2f} seconds!")
    print(f"[OK] SQLite Database:   data/creditpulse.db")
    print(f"[OK] Processed Tables:  data/processed/")
    print(f"[OK] Visual Artifacts:  artifacts/")
    print(f"[OK] Underwriting Docs: docs/underwriting_exception_audit.md")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
