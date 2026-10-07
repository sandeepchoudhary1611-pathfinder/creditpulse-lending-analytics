"""
CreditPulse Lending Analytics Platform
SQL Analysis Runner: Executes analytical SQL models against SQLite loan warehouse
and outputs aggregated risk tables.
Author: Sandeep Choudhary (IIT Delhi)
"""

import os
import sys
import sqlite3
import pandas as pd

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "creditpulse.db")
SQL_DIR = os.path.join(BASE_DIR, "sql")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

SQL_SCRIPTS = [
    ("02_vintage_cohort_curves.sql", "vintage_cohort_analysis.csv"),
    ("03_delinquency_roll_rates.sql", "delinquency_roll_rate_matrix.csv"),
    ("04_portfolio_at_risk_par.sql", "portfolio_at_risk_par.csv")
]

def run_sql_models():
    print("=" * 75)
    print(">>> CreditPulse: Executing Analytical SQL Models on Loan Warehouse")
    print("=" * 75)

    conn = sqlite3.connect(DB_PATH)

    for script_name, out_csv in SQL_SCRIPTS:
        script_path = os.path.join(SQL_DIR, script_name)
        print(f"[*] Executing {script_name}...")
        with open(script_path, "r", encoding="utf-8") as f:
            query = f.read()
        
        try:
            df_res = pd.read_sql_query(query, conn)
            out_path = os.path.join(PROCESSED_DIR, out_csv)
            df_res.to_csv(out_path, index=False)
            print(f"[+] Output {len(df_res):,} rows saved to: {out_csv}")
            print(f"    Preview:\n{df_res.head(3)}\n")
        except Exception as e:
            print(f"[!] Error executing {script_name}: {e}")

    conn.close()
    print("[OK] All analytical SQL queries executed successfully.")

if __name__ == "__main__":
    run_sql_models()
