"""
CreditPulse Lending Analytics Platform
Credit Risk Scoring & Probability of Default (PD) Engine
Author: Sandeep Choudhary (IIT Delhi)
Description:
    Trains and validates dual credit scorecards:
    1. Interpretable Logistic Scorecard (Regulatory Baseline)
    2. Gradient Boosted Classifier (HistGradientBoosting / LightGBM tier)
    Computes ROC-AUC, Gini (2*AUC - 1), KS-Statistic, Brier calibration,
    Expected Loss (EL = PD * LGD * EAD), and generates production risk artifacts.
"""

import os
import sys
import math
import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
    average_precision_score,
    confusion_matrix,
    classification_report,
    brier_score_loss
)

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "creditpulse.db")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# Plotting style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'Arial'
plt.rcParams['axes.edgecolor'] = '#cccccc'
plt.rcParams['axes.linewidth'] = 0.8

def calculate_ks_statistic(y_true, y_prob):
    """Calculates Kolmogorov-Smirnov (KS) statistic and optimal score threshold."""
    df = pd.DataFrame({'y_true': y_true, 'y_prob': y_prob})
    df = df.sort_values(by='y_prob', ascending=False).reset_index(drop=True)
    
    total_bads = df['y_true'].sum()
    total_goods = len(df) - total_bads
    
    df['cum_bads'] = df['y_true'].cumsum()
    df['cum_goods'] = (1 - df['y_true']).cumsum()
    
    df['cum_bads_pct'] = df['cum_bads'] / total_bads
    df['cum_goods_pct'] = df['cum_goods'] / total_goods
    df['ks'] = np.abs(df['cum_bads_pct'] - df['cum_goods_pct'])
    
    max_ks_idx = df['ks'].idxmax()
    ks_stat = df.loc[max_ks_idx, 'ks'] * 100.0
    optimal_threshold = df.loc[max_ks_idx, 'y_prob']
    
    return ks_stat, optimal_threshold

def run_credit_scoring_pipeline():
    print("=" * 75)
    print(">>> CreditPulse: Running Quantitative Credit Scoring & Risk Modeling Pipeline")
    print("=" * 75)

    # 1. Load Data from SQLite View
    print("[*] Fetching origination feature store from view_underwriting_ml_features...")
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            loan_id,
            borrower_id,
            origination_date,
            product_category,
            secured_flag,
            disbursed_principal_inr,
            tenor_months,
            annual_interest_rate,
            monthly_emi_inr,
            loan_purpose,
            age,
            employment_type,
            monthly_income_inr,
            city_tier,
            residence_ownership,
            cibil_score,
            bureau_total_accounts,
            bureau_active_loans_count,
            total_existing_monthly_emi,
            debt_to_income_ratio,
            credit_utilization_ratio,
            bureau_inquiries_last_30d,
            bureau_inquiries_last_90d,
            historical_dpd_max_last_12m,
            total_inquiries_pre_loan,
            unsecured_inquiries_pre_loan,
            installment_to_income_ratio,
            loan_to_annual_income_ratio,
            total_dti_ratio,
            credit_risk_segment,
            target_default_12m
        FROM view_underwriting_ml_features
    """
    df = pd.read_sql_query(query, conn)
    print(f"[+] Loaded {len(df):,} loans. Total defaults (90+ DPD in 12M): {df['target_default_12m'].sum():,} ({df['target_default_12m'].mean()*100:.2f}%)")

    # 2. Define Features
    numeric_features = [
        'cibil_score',
        'monthly_income_inr',
        'disbursed_principal_inr',
        'annual_interest_rate',
        'tenor_months',
        'monthly_emi_inr',
        'bureau_total_accounts',
        'bureau_active_loans_count',
        'debt_to_income_ratio',
        'credit_utilization_ratio',
        'bureau_inquiries_last_30d',
        'bureau_inquiries_last_90d',
        'historical_dpd_max_last_12m',
        'total_inquiries_pre_loan',
        'unsecured_inquiries_pre_loan',
        'installment_to_income_ratio',
        'loan_to_annual_income_ratio',
        'total_dti_ratio',
        'age'
    ]

    categorical_features = [
        'product_category',
        'secured_flag',
        'loan_purpose',
        'employment_type',
        'city_tier',
        'residence_ownership'
    ]

    X = df[numeric_features + categorical_features]
    y = df['target_default_12m']

    # 3. Train/Test Split (Stratified 80/20)
    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, df.index, test_size=0.20, random_state=42, stratify=y
    )
    print(f"[*] Train set: {len(X_train):,} samples | Test set: {len(X_test):,} samples")

    # 4. Preprocessing Transformers
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numeric_features),
            ('cat', OneHotEncoder(drop='first', sparse_output=False, handle_unknown='ignore'), categorical_features)
        ]
    )

    # 5. Model 1: Logistic Regression Scorecard (Industry Benchmark)
    print("[*] Training Regulatory Logistic Regression Scorecard...")
    log_reg_pipeline = Pipeline(steps=[
        ('prep', preprocessor),
        ('clf', LogisticRegression(max_iter=1000, random_state=42, C=0.8, class_weight='balanced'))
    ])
    log_reg_pipeline.fit(X_train, y_train)
    y_prob_logreg = log_reg_pipeline.predict_proba(X_test)[:, 1]

    auc_logreg = roc_auc_score(y_test, y_prob_logreg)
    gini_logreg = 2 * auc_logreg - 1
    ks_logreg, ks_thresh_logreg = calculate_ks_statistic(y_test.values, y_prob_logreg)

    print(f"    - Logistic Reg ROC-AUC: {auc_logreg:.4f} | Gini: {gini_logreg:.4f} | KS: {ks_logreg:.2f}%")

    # 6. Model 2: Gradient Boosted Trees (HistGradientBoosting / LightGBM)
    print("[*] Training Production Gradient Boosted Classifier (HistGradientBoosting)...")
    # For HistGradientBoosting, preprocess categoricals
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)

    hgb_model = HistGradientBoostingClassifier(
        max_iter=150,
        learning_rate=0.08,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        random_state=42,
        class_weight='balanced'
    )
    hgb_model.fit(X_train_proc, y_train)
    y_prob_hgb = hgb_model.predict_proba(X_test_proc)[:, 1]

    auc_hgb = roc_auc_score(y_test, y_prob_hgb)
    gini_hgb = 2 * auc_hgb - 1
    ks_hgb, ks_thresh_hgb = calculate_ks_statistic(y_test.values, y_prob_hgb)
    brier_hgb = brier_score_loss(y_test, y_prob_hgb)

    print(f"    - Gradient Boost ROC-AUC: {auc_hgb:.4f} | Gini: {gini_hgb:.4f} | KS: {ks_hgb:.2f}% | Brier: {brier_hgb:.4f}")

    # Select Champion Model: HistGradientBoosting
    champion_pipeline = hgb_model
    y_prob_champ = y_prob_hgb
    optimal_cutoff = ks_thresh_hgb
    y_pred_champ = (y_prob_champ >= optimal_cutoff).astype(int)

    cm = confusion_matrix(y_test, y_pred_champ)
    print(f"[+] Optimal Risk Cutoff: {optimal_cutoff:.4f}")
    print(f"[+] Confusion Matrix:\n{cm}")
    print("\nClassification Report:\n", classification_report(y_test, y_pred_champ, digits=4))

    # 7. Score Whole Portfolio & Compute Expected Loss (EL = PD * LGD * EAD)
    print("[*] Generating portfolio-wide Underwriting Scores and Expected Loss...")
    X_all_proc = preprocessor.transform(X)
    df['predicted_pd'] = champion_pipeline.predict_proba(X_all_proc)[:, 1]
    
    # Standard FICO-style credit score scaling: Base 600 at 5% odds, 20 points doubles odds
    # Score = 650 - (50 / ln(2)) * ln(PD / (1 - PD))
    def pd_to_score(pd_val):
        odds = max(0.001, min(0.999, pd_val)) / (1.0 - max(0.001, min(0.999, pd_val)))
        raw_score = 650 - (40 / math.log(2)) * math.log(odds)
        return int(round(max(300, min(850, raw_score))))

    df['creditpulse_internal_score'] = df['predicted_pd'].apply(pd_to_score)
    
    # Expected Loss calculation: EL = PD * LGD * EAD
    # LGD: 0.70 for unsecured personal loans/BNPL, 0.40 for secured auto/mortgage
    df['lgd_factor'] = df['secured_flag'].apply(lambda s: 0.40 if s == 1 else 0.70)
    df['ead_inr'] = df['disbursed_principal_inr']
    df['expected_loss_inr'] = round(df['predicted_pd'] * df['lgd_factor'] * df['ead_inr'], 2)

    # Underwriting Policy Decision Engine
    # Cutoffs:
    # PD < 0.10: Auto-Approve
    # 0.10 <= PD < 0.25: Borderline Referral / Manual Underwriting (Ops Triage)
    # PD >= 0.25: Auto-Decline
    def underwriting_action(pd_val):
        if pd_val < 0.12:
            return "AUTO_APPROVE"
        elif pd_val < 0.28:
            return "REFERRAL_TRIAGE"
        else:
            return "AUTO_DECLINE"

    df['underwriting_decision'] = df['predicted_pd'].apply(underwriting_action)

    # 8. Save Scored Dataset to SQLite & CSV
    scored_cols = [
        'loan_id', 'borrower_id', 'cibil_score', 'creditpulse_internal_score',
        'predicted_pd', 'lgd_factor', 'ead_inr', 'expected_loss_inr',
        'underwriting_decision', 'target_default_12m'
    ]
    df_scored = df[scored_cols]

    print("[*] Persisting fact_loan_underwriting_scores table into SQLite...")
    df_scored.to_sql("fact_loan_underwriting_scores", conn, if_exists="replace", index=False)
    
    # Save CSVs
    scored_csv_path = os.path.join(PROCESSED_DIR, "scored_loans_underwriting.csv")
    df.to_csv(scored_csv_path, index=False)
    print(f"[+] Saved full scored dataset to: {scored_csv_path}")

    # Portfolio Risk Summary by Segment
    portfolio_summary = df.groupby('underwriting_decision').agg(
        total_loans=('loan_id', 'count'),
        total_disbursed_inr=('disbursed_principal_inr', 'sum'),
        avg_cibil=('cibil_score', 'mean'),
        avg_predicted_pd=('predicted_pd', 'mean'),
        total_expected_loss_inr=('expected_loss_inr', 'sum'),
        actual_default_rate_pct=('target_default_12m', lambda x: x.mean() * 100)
    ).reset_index()

    summary_csv_path = os.path.join(PROCESSED_DIR, "portfolio_risk_summary.csv")
    portfolio_summary.to_csv(summary_csv_path, index=False)
    print(f"[+] Saved portfolio risk summary to: {summary_csv_path}")

    # 9. Generate High-Res Visual Artifacts
    print("[*] Generating Publication-Grade Visual Artifacts...")

    # Artifact 1: ROC & Precision-Recall Curves
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300)
    fpr_log, tpr_log, _ = roc_curve(y_test, y_prob_logreg)
    fpr_hgb, tpr_hgb, _ = roc_curve(y_test, y_prob_hgb)

    ax1.plot(fpr_hgb, tpr_hgb, color='#0066cc', lw=2.5, label=f'HistGradientBoosting (AUC = {auc_hgb:.3f}, Gini = {gini_hgb:.3f})')
    ax1.plot(fpr_log, tpr_log, color='#e67e22', lw=2, linestyle='--', label=f'Logistic Regression (AUC = {auc_logreg:.3f}, Gini = {gini_logreg:.3f})')
    ax1.plot([0, 1], [0, 1], color='#888888', linestyle=':', lw=1.2, label='Random Chance (AUC = 0.50)')
    ax1.set_title('Credit Risk Scorecard: ROC Discrimination Curves', fontsize=13, fontweight='bold', pad=12)
    ax1.set_xlabel('False Positive Rate (Type I Error)', fontsize=11)
    ax1.set_ylabel('True Positive Rate (Sensitivity / Recall)', fontsize=11)
    ax1.legend(loc='lower right', frameon=True, fontsize=10)
    ax1.grid(True, linestyle='--', alpha=0.6)

    # PR Curve
    prec, rec, _ = precision_recall_curve(y_test, y_prob_hgb)
    pr_auc = average_precision_score(y_test, y_prob_hgb)
    ax2.plot(rec, prec, color='#27ae60', lw=2.5, label=f'PR Curve (AP = {pr_auc:.3f})')
    ax2.axhline(y=y_test.mean(), color='#888888', linestyle=':', label=f'Baseline Event Rate ({y_test.mean()*100:.1f}%)')
    ax2.set_title('Precision-Recall Curve (Default Class Imbalance)', fontsize=13, fontweight='bold', pad=12)
    ax2.set_xlabel('Recall (Bad Loans Captured)', fontsize=11)
    ax2.set_ylabel('Precision (True Delinquents / Predicted)', fontsize=11)
    ax2.legend(loc='upper right', frameon=True, fontsize=10)
    ax2.grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    fig.savefig(os.path.join(ARTIFACTS_DIR, "pd_roc_curve.png"), bbox_inches='tight')
    plt.close()

    # Artifact 2: Confusion Matrix & Optimal Cutoff
    fig, ax = plt.subplots(figsize=(7, 6), dpi=300)
    cm_norm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    sns.heatmap(
        cm, annot=True, fmt=',d', cmap='Blues', cbar=False,
        xticklabels=['Predicted Non-Default', 'Predicted Default'],
        yticklabels=['Actual Non-Default', 'Actual Default'],
        ax=ax, annot_kws={"size": 13, "weight": "bold"}
    )
    # Overlay percentages
    for i in range(2):
        for j in range(2):
            ax.text(j + 0.5, i + 0.72, f"({cm_norm[i, j]*100:.1f}%)",
                    ha='center', va='center', color='darkslategray', fontsize=10)

    ax.set_title(f'Delinquency Classification Matrix\n(Optimal Threshold = {optimal_cutoff:.3f} | KS = {ks_hgb:.1f}%)',
                 fontsize=12, fontweight='bold', pad=12)
    plt.tight_layout()
    fig.savefig(os.path.join(ARTIFACTS_DIR, "delinquency_confusion_matrix.png"), bbox_inches='tight')
    plt.close()

    # Artifact 3: Score Separation & KS Curve
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    sns.kdeplot(df.loc[df['target_default_12m'] == 0, 'creditpulse_internal_score'],
                label='Non-Defaulting Loans (Good)', color='#2980b9', fill=True, alpha=0.35, lw=2, ax=ax)
    sns.kdeplot(df.loc[df['target_default_12m'] == 1, 'creditpulse_internal_score'],
                label='Defaulted Loans (Bad 90+ DPD)', color='#c0392b', fill=True, alpha=0.35, lw=2, ax=ax)
    ax.axvline(x=600, color='#d35400', linestyle='--', lw=1.8, label=f'Policy Referral Boundary (Cutoff: ~600)')
    ax.set_title(f'CreditPulse Internal Score Distribution: Goods vs. Bads Separation (KS: {ks_hgb:.1f}%)',
                 fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel('Internal Risk Score (300 to 850)', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.legend(frameon=True, fontsize=10)
    ax.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    fig.savefig(os.path.join(ARTIFACTS_DIR, "score_distribution_by_default.png"), bbox_inches='tight')
    plt.close()

    # Artifact 4: Feature Importance
    # Extract feature names from preprocessor
    num_names = numeric_features
    cat_encoder = preprocessor.named_transformers_['cat']
    cat_names = list(cat_encoder.get_feature_names_out(categorical_features))
    all_feature_names = num_names + cat_names

    # Use logistic regression absolute coefficients as normalized interpretable weights
    coefs = np.abs(log_reg_pipeline.named_steps['clf'].coef_[0])
    feat_df = pd.DataFrame({'feature': all_feature_names, 'importance': coefs})
    feat_df = feat_df.sort_values(by='importance', ascending=False).head(14)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    colors = ['#0055aa' if i < 3 else '#4a90e2' for i in range(len(feat_df))]
    sns.barplot(x='importance', y='feature', data=feat_df, palette=colors, ax=ax)
    ax.set_title('Top Credit Underwriting Risk Drivers (Scorecard Feature Weight)', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel('Normalized Magnitude (|Logistic Beta Weight|)', fontsize=11)
    ax.set_ylabel('Model Risk Attribute', fontsize=11)
    ax.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    fig.savefig(os.path.join(ARTIFACTS_DIR, "credit_feature_importance.png"), bbox_inches='tight')
    plt.close()

    # Artifact 5: Vintage Maturation Curves
    print("[*] Generating Vintage Maturation Curves from fact_repayment_schedule...")
    vintage_query = """
        SELECT
            strftime('%Y', l.origination_date) || '-Q' ||
                CAST(((CAST(strftime('%m', l.origination_date) AS INT) - 1) / 3) + 1 AS TEXT) AS vintage,
            r.installment_number AS mob,
            COUNT(DISTINCT r.loan_id) AS cohort_size,
            ROUND(SUM(CASE WHEN r.dpd_days >= 30 THEN 1 ELSE 0 END) * 100.0 / COUNT(DISTINCT r.loan_id), 2) AS cum_30p_dpd_pct,
            ROUND(SUM(CASE WHEN r.dpd_days >= 90 THEN 1 ELSE 0 END) * 100.0 / COUNT(DISTINCT r.loan_id), 2) AS cum_90p_dpd_pct
        FROM fact_loan_originations l
        JOIN fact_repayment_schedule r ON l.loan_id = r.loan_id
        WHERE r.installment_number <= 18
        GROUP BY vintage, mob
        ORDER BY vintage, mob
    """
    df_vintage = pd.read_sql_query(vintage_query, conn)

    fig, (v_ax1, v_ax2) = plt.subplots(1, 2, figsize=(15, 6), dpi=300)
    vintages = sorted(df_vintage['vintage'].unique())
    palette = sns.color_palette("tab10", len(vintages))

    for i, v in enumerate(vintages):
        v_sub = df_vintage[df_vintage['vintage'] == v]
        v_ax1.plot(v_sub['mob'], v_sub['cum_30p_dpd_pct'], marker='o', markersize=4, label=v, color=palette[i], lw=2)
        v_ax2.plot(v_sub['mob'], v_sub['cum_90p_dpd_pct'], marker='s', markersize=4, label=v, color=palette[i], lw=2)

    v_ax1.set_title('Vintage Maturation Curve: Cumulative 30+ DPD % by MOB', fontsize=12, fontweight='bold', pad=12)
    v_ax1.set_xlabel('Months on Book (MOB)', fontsize=11)
    v_ax1.set_ylabel('Cumulative Delinquency Rate (30+ DPD %)', fontsize=11)
    v_ax1.legend(title='Vintage Cohort', frameon=True, fontsize=9)
    v_ax1.grid(True, linestyle='--', alpha=0.6)

    v_ax2.set_title('Vintage Maturation Curve: Cumulative 90+ DPD (GNPA %) by MOB', fontsize=12, fontweight='bold', pad=12)
    v_ax2.set_xlabel('Months on Book (MOB)', fontsize=11)
    v_ax2.set_ylabel('Cumulative Default Rate (90+ DPD %)', fontsize=11)
    v_ax2.legend(title='Vintage Cohort', frameon=True, fontsize=9)
    v_ax2.grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    fig.savefig(os.path.join(ARTIFACTS_DIR, "vintage_maturation_curves.png"), bbox_inches='tight')
    plt.close()

    conn.close()
    print("[OK] Credit Scoring Pipeline Completed Successfully.")
    print(f"[OK] Visual artifacts saved to: {ARTIFACTS_DIR}")

if __name__ == "__main__":
    run_credit_scoring_pipeline()
