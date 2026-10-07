"""
CreditPulse Lending Analytics Platform
AI Credit Underwriting Copilot & Borderline Referral Triage
Author: Sandeep Choudhary (IIT Delhi)
Description:
    Triages borderline loan applications (CIBIL 650-710, Referral status)
    generating structured Credit Committee Exception Memos, risk rationale,
    and policy covenant recommendations.
    Uses Gemini 2.5 Flash via google-genai SDK, with deterministic rule-based
    credit underwriting policy fallback.
"""

import os
import sys
import json
import sqlite3
import pandas as pd
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "creditpulse.db")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
DOCS_DIR = os.path.join(BASE_DIR, "docs")

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

def generate_rule_based_memo(applicant: dict) -> dict:
    """Deterministic FinTech Credit Committee heuristic fallback."""
    cibil = applicant['cibil_score']
    dti = applicant['total_dti_ratio']
    util = applicant['credit_utilization_ratio']
    inq = applicant['bureau_inquiries_last_30d']
    amt = applicant['disbursed_principal_inr']
    prod = applicant['product_category']
    pd_score = applicant['predicted_pd']

    compensating_factors = []
    risk_flags = []

    # Risk factor diagnostics
    if cibil >= 680:
        compensating_factors.append(f"Near-prime bureau score ({cibil}) indicates historical repayment intent.")
    else:
        risk_flags.append(f"Sub-prime bureau score ({cibil}) reflects elevated delinquency susceptibility.")

    if dti < 0.45:
        compensating_factors.append(f"Healthy total debt-to-income ({dti:.1%}) within safe debt servicing threshold (<50%).")
    else:
        risk_flags.append(f"Elevated DTI ({dti:.1%}) poses cash flow squeeze during income shocks.")

    if util < 0.50:
        compensating_factors.append(f"Conservative credit line utilization ({util:.1%}) indicates credit headroom.")
    else:
        risk_flags.append(f"High revolving credit line utilization ({util:.1%}) flags potential liquidity strain.")

    if inq <= 1:
        compensating_factors.append(f"Low recent inquiry velocity ({inq} in last 30d) demonstrates controlled credit seeking.")
    else:
        risk_flags.append(f"Aggressive credit seeking behavior detected ({inq} bureau hard pulls in past 30 days).")

    # Final policy decision
    score_metric = (1.0 if cibil >= 680 else 0.0) + (1.0 if dti < 0.45 else 0.0) + (1.0 if util < 0.55 else 0.0) + (1.0 if inq <= 1 else 0.0)

    if score_metric >= 3.0:
        decision = "APPROVE_WITH_RISK_COVENANTS"
        sanction_amt = amt
        covenants = [
            "Mandate automated e-NACH mandate via Primary Salary Bank Account.",
            "Apply risk-adjusted pricing premium (+75 bps APR).",
            "Cap credit limit enhancements for the first 6 months on book."
        ]
        rationale = "Strong debt-servicing capacity and clean recent credit discipline offset borderline bureau score."
    elif score_metric == 2.0:
        decision = "APPROVE_WITH_REDUCED_SANCTION"
        sanction_amt = round(amt * 0.75 / 5000) * 5000
        covenants = [
            f"Haircut ticket size by 25% from INR {amt:,.0f} to INR {sanction_amt:,.0f}.",
            "Require co-borrower / spouse guarantee or primary asset lien.",
            "Set repayment date to 5th of each month post salary credit."
        ]
        rationale = "Applicant demonstrates viable earning capacity but displays elevated debt load; ticket curtailment mitigates EAD."
    else:
        decision = "DECLINE_REFERRAL"
        sanction_amt = 0
        covenants = [
            "Issue Adverse Action Notice advising reduction of revolving credit balances.",
            "Re-application eligibility period: 90 days post bureau stabilization."
        ]
        rationale = "Multiple compounding adverse flags (high leverage, multi-inquiry spikes, subprime score) exceed portfolio risk appetite."

    return {
        "loan_id": applicant['loan_id'],
        "borrower_id": applicant['borrower_id'],
        "application_date": applicant['origination_date'],
        "product_type": prod,
        "requested_amount_inr": amt,
        "predicted_pd": round(pd_score, 4),
        "internal_score": applicant['creditpulse_internal_score'],
        "underwriting_verdict": decision,
        "recommended_sanction_inr": sanction_amt,
        "compensating_factors": compensating_factors,
        "risk_flags": risk_flags,
        "prescribed_policy_covenants": covenants,
        "underwriter_memo_narrative": rationale,
        "evaluation_timestamp": datetime.now().isoformat(),
        "engine": "CreditPulse Heuristic Policy Engine v2.4"
    }

def generate_llm_memo(applicant: dict, client) -> dict:
    """Uses Gemini 2.5 Flash via google-genai to synthesize credit memo."""
    prompt = f"""
You are the Chief Credit Officer at a premier digital lending FinTech (e.g., Navi / CRED / Bajaj Finance).
Analyze the following borderline loan applicant flagged for referral triage and generate a rigorous credit underwriting memo.

APPLICANT PROFILE:
- Loan ID: {applicant['loan_id']}
- Borrower ID: {applicant['borrower_id']}
- Product: {applicant['product_category']} (Secured: {applicant['secured_flag']})
- Requested Amount: INR {applicant['disbursed_principal_inr']:,.2f}
- Tenure: {applicant['tenor_months']} months | Interest Rate: {applicant['annual_interest_rate']}%
- Monthly Income: INR {applicant['monthly_income_inr']:,.2f}
- Employment Type: {applicant['employment_type']}
- City: {applicant['city']} ({applicant['city_tier']}) | Residence: {applicant['residence_ownership']}
- CIBIL Score: {applicant['cibil_score']}
- Credit Utilization Ratio: {applicant['credit_utilization_ratio']:.1%}
- Total Debt-to-Income (DTI): {applicant['total_dti_ratio']:.1%}
- Bureau Inquiries (Last 30 Days): {applicant['bureau_inquiries_last_30d']}
- Predicted Probability of Default (PD): {applicant['predicted_pd']:.2%}
- CreditPulse Internal Risk Score: {applicant['creditpulse_internal_score']} / 850

Return ONLY a valid JSON object matching this schema:
{{
  "loan_id": "{applicant['loan_id']}",
  "borrower_id": "{applicant['borrower_id']}",
  "underwriting_verdict": "APPROVE_WITH_RISK_COVENANTS | APPROVE_WITH_REDUCED_SANCTION | DECLINE_REFERRAL",
  "recommended_sanction_inr": <number>,
  "compensating_factors": ["string", "string"],
  "risk_flags": ["string", "string"],
  "prescribed_policy_covenants": ["string", "string"],
  "underwriter_memo_narrative": "Comprehensive narrative analyzing creditworthiness, default risk, and rationale."
}}
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'temperature': 0.2
            }
        )
        memo = json.loads(response.text)
        memo["requested_amount_inr"] = applicant['disbursed_principal_inr']
        memo["predicted_pd"] = round(applicant['predicted_pd'], 4)
        memo["internal_score"] = applicant['creditpulse_internal_score']
        memo["evaluation_timestamp"] = datetime.now().isoformat()
        memo["engine"] = "Gemini 2.5 Flash Autonomous Underwriter"
        return memo
    except Exception as e:
        print(f"[!] Gemini API call failed ({e}). Falling back to deterministic rule engine.")
        return generate_rule_based_memo(applicant)

def run_ai_underwriting_triage():
    print("=" * 75)
    print(">>> CreditPulse: Running AI Credit Underwriting Copilot & Referral Triage")
    print("=" * 75)

    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            f.loan_id,
            f.borrower_id,
            f.origination_date,
            f.product_category,
            f.secured_flag,
            f.disbursed_principal_inr,
            f.tenor_months,
            f.annual_interest_rate,
            f.monthly_income_inr,
            f.employment_type,
            f.city,
            f.city_tier,
            f.residence_ownership,
            f.cibil_score,
            f.credit_utilization_ratio,
            f.total_dti_ratio,
            f.bureau_inquiries_last_30d,
            s.predicted_pd,
            s.creditpulse_internal_score,
            s.underwriting_decision
        FROM view_underwriting_ml_features f
        JOIN fact_loan_underwriting_scores s ON f.loan_id = s.loan_id
        WHERE s.underwriting_decision = 'REFERRAL_TRIAGE'
        LIMIT 25
    """
    df_referrals = pd.read_sql_query(query, conn)
    conn.close()

    print(f"[+] Retrieved {len(df_referrals)} borderline referral cases for underwriting triage.")

    # Initialize Gemini client if API key is present
    gemini_client = None
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            gemini_client = genai.Client(api_key=api_key)
            print("[+] Initialized Gemini 2.5 Flash Underwriting Client.")
        except Exception as e:
            print(f"[!] Warning: Could not initialize Gemini client: {e}")
    else:
        print("[i] GEMINI_API_KEY not found in environment. Using Built-in FinTech Policy Engine.")

    triage_results = []
    print("[*] Processing referral cases through Underwriting Engine...")
    for idx, row in df_referrals.iterrows():
        app_dict = row.to_dict()
        if gemini_client and idx < 5:  # Run first 5 with Gemini if active
            memo = generate_llm_memo(app_dict, gemini_client)
        else:
            memo = generate_rule_based_memo(app_dict)
        triage_results.append(memo)

    # Save to JSON
    json_path = os.path.join(PROCESSED_DIR, "underwriting_exception_memos.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(triage_results, f, indent=2)
    print(f"[+] Saved {len(triage_results)} exception memos to: {json_path}")

    # Generate Markdown Audit Report
    md_path = os.path.join(DOCS_DIR, "underwriting_exception_audit.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# CreditPulse Underwriting Exception & Referral Triage Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Underwriting Policy Framework:** FinTech Digital NBFC Risk Standards  \n")
        f.write(f"**Total Referrals Triaged:** {len(triage_results)}\n\n")
        f.write("---\n\n")
        
        for i, m in enumerate(triage_results[:8], 1):
            f.write(f"### Case #{i}: Loan `{m['loan_id']}` (Borrower: `{m['borrower_id']}`)\n\n")
            f.write(f"- **Requested Amount:** INR {m.get('requested_amount_inr', 0):,.2f}\n")
            f.write(f"- **Model Probability of Default (PD):** {m['predicted_pd']:.2%}\n")
            f.write(f"- **Internal Score:** {m['internal_score']} / 850\n")
            f.write(f"- **Underwriting Verdict:** **`{m['underwriting_verdict']}`**\n")
            f.write(f"- **Sanctioned Amount:** INR {m.get('recommended_sanction_inr', 0):,.2f}\n")
            f.write(f"- **Underwriter Memo:** {m['underwriter_memo_narrative']}\n\n")
            
            f.write("**Compensating Strengths:**\n")
            for comp in m.get('compensating_factors', []):
                f.write(f"  * {comp}\n")
                
            f.write("\n**Key Risk Flags:**\n")
            for flg in m.get('risk_flags', []):
                f.write(f"  * {flg}\n")
                
            f.write("\n**Policy Covenants & Mitigation Controls:**\n")
            for cov in m.get('prescribed_policy_covenants', []):
                f.write(f"  * {cov}\n")
            f.write("\n---\n\n")

    print(f"[+] Saved Underwriting Audit Report to: {md_path}")
    print("[OK] AI Credit Underwriting Copilot Run Completed Successfully.")

if __name__ == "__main__":
    run_ai_underwriting_triage()
