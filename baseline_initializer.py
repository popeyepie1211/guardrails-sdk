"""
baseline_initializer.py

Bootstrap baseline statistics for a new model.
Processes a training/historical dataset to compute mean and std for all vitals.
Saves baseline and metadata for later use by the worker.

Usage:
    python baseline_initializer.py --model_id loan_risk_v1 --data data/train.csv --domain finance

Outputs:
    baselines/loan_risk_v1.json           (baseline summary)
    baselines/loan_risk_v1_metadata.json  (model metadata)
"""

import json
import os
import argparse
import logging
import pandas as pd
import numpy as np
import psycopg
from typing import Dict, Any

# Core Engine Imports
from guardrail_ai.core.vitals_engine import VitalsEngine
from guardrail_ai.metrics.fairness import StatisticalParity, GiniCoefficient
from guardrail_ai.metrics.privacy import PrivacyScore
from guardrail_ai.metrics.stability import PSI
from guardrail_ai.metrics.transparency import SHAPExplainability
from guardrail_ai.metrics.security import Security

# ============================================
# LOGGING
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'postgres')

# ============================================
# BASELINE COMPUTATION
# ============================================
def compute_baseline(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    window_size: int = 100
) -> Dict[str, Any]:
    """
    Compute baseline statistics from historical data.
    
    Splits data into windows and computes each metric repeatedly,
    then aggregates mean and std.
    
    Args:
        df: Historical dataset
        metadata: Model metadata with feature/prediction columns
        window_size: Size of each window for metric computation
    
    Returns:
        Baseline summary with mean and std for all vitals
    """
    baseline_summary = {}
    
    feature_cols = metadata.get("feature_columns", [])
    pred_col = metadata.get("prediction_column", "prediction")
    numerical_features = metadata.get("numerical_features", [])
    categorical_features = metadata.get("categorical_features", [])
    protected_attrs = metadata.get("protected_attributes")
    quasi_ids = metadata.get("quasi_identifier_columns", [])
    
    logger.info(f"📊 Computing baseline from {len(df)} historical records...")
    
    # Split into windows
    metrics_history = {
        "gini": [],
        "psi": [],
        "linf": [],
        "ood_score": [],
        "privacy_score": [],
        "shap_importance": [],
    }
    
    if protected_attrs:
        metrics_history["statistical_parity"] = []
    
    # Process windows
    num_windows = max(1, len(df) // window_size)
    for i in range(num_windows):
        start_idx = i * window_size
        end_idx = min((i + 1) * window_size, len(df))
        window_df = df.iloc[start_idx:end_idx].copy()
        
        if len(window_df) < 10:  # Skip tiny windows
            continue
        
        # Gini
        preds = window_df[pred_col].values
        try:
            gini_val = GiniCoefficient.compute(preds)
            metrics_history["gini"].append(gini_val)
        except Exception as e:
            logger.warning(f"⚠️  Gini computation failed: {e}")
        
        # Privacy Score
        try:
            privacy_val = PrivacyScore.compute(window_df, quasi_ids)
            metrics_history["privacy_score"].append(privacy_val)
        except Exception as e:
            logger.warning(f"⚠️  Privacy score computation failed: {e}")
        
        # PSI (Population Stability Index)
        psi_values = []
        for col in numerical_features:
            try:
                actual = window_df[col].values
                baseline_mean = np.mean(actual)
                expected = np.full(len(actual), baseline_mean)
                psi_val = PSI.compute_psi(expected, actual)
                psi_values.append(psi_val)
            except Exception as e:
                logger.warning(f"⚠️  PSI computation for {col} failed: {e}")
        if psi_values:
            metrics_history["psi"].append(np.mean(psi_values))
        
        # Security (L∞ + OOD)
        linf_values = []
        ood_values = []
        for col in numerical_features:
            try:
                actual = window_df[col].values
                baseline_mean = np.mean(actual)
                expected = np.full(len(actual), baseline_mean)
                sec = Security.compute(expected, actual)
                linf_values.append(sec.get("linf", 0))
                ood_values.append(sec.get("ood_score", 0))
            except Exception as e:
                logger.warning(f"⚠️  Security computation for {col} failed: {e}")
        if linf_values:
            metrics_history["linf"].append(np.mean(linf_values))
        if ood_values:
            metrics_history["ood_score"].append(np.mean(ood_values))
        
        # SHAP (now computed dynamically in worker_auditor.py)
        # Baseline aggregates SHAP results from actual worker batches
        # For baseline initialization, use placeholder until worker provides real data
        metrics_history["shap_importance"].append(0.5)
        
        # Statistical Parity (if fairness enabled)
        if protected_attrs:
            try:
                sp_val = StatisticalParity.compute(
                    df=window_df,
                    prediction_column=pred_col,
                    protected_attributes=protected_attrs
                )
                metrics_history["statistical_parity"].append(sp_val)
            except Exception as e:
                logger.warning(f"⚠️  Statistical parity computation failed: {e}")
    
    # Aggregate: compute mean and std
    for metric_name, values in metrics_history.items():
        if values:
            baseline_summary[metric_name] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)) if len(values) > 1 else 0.01
            }
            logger.info(f"  {metric_name}: mean={baseline_summary[metric_name]['mean']:.4f}, std={baseline_summary[metric_name]['std']:.4f}")
        else:
            logger.warning(f"  {metric_name}: No valid values, using defaults")
            baseline_summary[metric_name] = {"mean": 0.5, "std": 0.1}
    
    return {"baseline_summary": baseline_summary}

# ============================================
# METADATA BUILDER
# ============================================
def build_metadata(
    df: pd.DataFrame,
    feature_columns: list,
    prediction_column: str,
    domain: str,
    numerical_features: list,
    categorical_features: list,
    protected_attributes: Dict[str, Any] = None,
    quasi_identifier_columns: list = None
) -> Dict[str, Any]:
    """
    Build model metadata.
    """
    metadata = {
        "domain": domain,
        "feature_columns": feature_columns,
        "prediction_column": prediction_column,
        "prediction_type": "binary",
        "numerical_features": numerical_features,
        "categorical_features": categorical_features,
        "protected_attributes": protected_attributes,
        "quasi_identifier_columns": quasi_identifier_columns or categorical_features,
    }
    
    logger.info(f"✅ Built metadata for domain={domain}, features={len(feature_columns)}")
    return metadata

# ============================================
# FILE PERSISTENCE
# ============================================
def save_baseline(
    model_id: str,
    baseline: Dict[str, Any],
    metadata: Dict[str, Any],
    output_dir: str = "baselines"
) -> None:
    """
    Save baseline and metadata to JSON files.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    baseline_path = os.path.join(output_dir, f"{model_id}.json")
    metadata_path = os.path.join(output_dir, f"{model_id}_metadata.json")
    
    with open(baseline_path, 'w') as f:
        json.dump(baseline, f, indent=2)
    logger.info(f"✅ Baseline saved to {baseline_path}")
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"✅ Metadata saved to {metadata_path}")


def save_baseline_to_db(
    model_id: str,
    model_name: str,
    domain: str,
    version: str,
    baseline: Dict[str, Any],
    metadata: Dict[str, Any],
) -> None:
    """Persist baseline + metadata into production tables."""
    conn = psycopg.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO models (model_id, model_name, domain)
                VALUES (%s, %s, %s)
                ON CONFLICT (model_id)
                DO UPDATE SET
                    model_name = EXCLUDED.model_name,
                    domain = EXCLUDED.domain,
                    updated_at = NOW();
                """,
                (model_id, model_name, domain),
            )

            cursor.execute(
                """
                INSERT INTO model_baselines (model_id, baseline, metadata, version)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (model_id)
                DO UPDATE SET
                    baseline = EXCLUDED.baseline,
                    metadata = EXCLUDED.metadata,
                    version = EXCLUDED.version,
                    updated_at = NOW();
                """,
                (model_id, json.dumps(baseline), json.dumps(metadata), version),
            )
        conn.commit()
        logger.info("✅ Baseline and metadata upserted into PostgreSQL")
    finally:
        conn.close()

# ============================================
# CLI
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap baseline statistics for a Guardrail AI model"
    )
    
    parser.add_argument(
        "--model_id",
        required=True,
        help="Unique model identifier (e.g., loan_risk_v1)"
    )
    parser.add_argument(
        "--data",
        required=True,
        help="Path to training/historical CSV data"
    )
    parser.add_argument(
        "--domain",
        default="finance",
        choices=["finance", "healthcare", "standard"],
        help="Model domain"
    )
    parser.add_argument(
        "--feature_columns",
        default="income,credit_score",
        help="Comma-separated list of feature column names"
    )
    parser.add_argument(
        "--prediction_column",
        default="prediction",
        help="Name of prediction column"
    )
    parser.add_argument(
        "--numerical_features",
        default="income,credit_score",
        help="Comma-separated list of numerical feature names"
    )
    parser.add_argument(
        "--categorical_features",
        default="gender",
        help="Comma-separated list of categorical feature names"
    )
    parser.add_argument(
        "--protected_column",
        default="gender",
        help="Name of protected attribute column (for fairness)"
    )
    parser.add_argument(
        "--output_dir",
        default="baselines",
        help="Output directory for baseline files"
    )
    parser.add_argument(
        "--window_size",
        type=int,
        default=100,
        help="Window size for metric computation"
    )
    parser.add_argument(
        "--model_version",
        default="v1",
        help="Semantic model version used by worker SHAP pipeline"
    )
    parser.add_argument(
        "--model_name",
        default=None,
        help="Human friendly model name (defaults to model_id)"
    )
    parser.add_argument(
        "--model_artifact_path",
        default=None,
        help="Path to serialized production model artifact used for SHAP"
    )
    parser.add_argument(
        "--preprocessor_artifact_path",
        default=None,
        help="Optional path to serialized preprocessor/pipeline artifact"
    )
    parser.add_argument(
        "--shap_background_path",
        default=None,
        help="CSV path used as deterministic SHAP background dataset"
    )
    parser.add_argument(
        "--skip_db_upsert",
        action="store_true",
        help="Skip writing baseline/metadata to PostgreSQL"
    )
    
    args = parser.parse_args()
    
    logger.info(f"🚀 Baseline Initializer starting...")
    
    # Load data
    logger.info(f"📂 Loading data from {args.data}")
    try:
        df = pd.read_csv(args.data)
        logger.info(f"✅ Loaded {len(df)} records")
    except Exception as e:
        logger.error(f"❌ Failed to load data: {e}")
        return
    
    # Parse columns
    feature_columns = [c.strip() for c in args.feature_columns.split(",")]
    numerical_features = [c.strip() for c in args.numerical_features.split(",")]
    categorical_features = [c.strip() for c in args.categorical_features.split(",")]
    
    # Build metadata
    protected_attrs = {
        "type": "categorical",
        "columns": [args.protected_column]
    } if args.protected_column in df.columns else None
    
    metadata = build_metadata(
        df,
        feature_columns=feature_columns,
        prediction_column=args.prediction_column,
        domain=args.domain,
        numerical_features=numerical_features,
        categorical_features=categorical_features,
        protected_attributes=protected_attrs,
        quasi_identifier_columns=categorical_features
    )
    metadata["model_version"] = args.model_version
    if args.model_artifact_path:
        metadata["model_artifact_path"] = args.model_artifact_path
    if args.preprocessor_artifact_path:
        metadata["preprocessor_artifact_path"] = args.preprocessor_artifact_path
    if args.shap_background_path:
        metadata["shap_background_path"] = args.shap_background_path
    metadata["shap_explainer_type"] = metadata.get("shap_explainer_type", "auto")
    
    # Compute baseline
    baseline = compute_baseline(df, metadata, window_size=args.window_size)
    
    # Save
    save_baseline(args.model_id, baseline, metadata, output_dir=args.output_dir)

    if not args.skip_db_upsert:
        save_baseline_to_db(
            model_id=args.model_id,
            model_name=args.model_name or args.model_id,
            domain=args.domain,
            version=args.model_version,
            baseline=baseline,
            metadata=metadata,
        )
    else:
        logger.warning("⚠️ Skipped DB upsert (--skip_db_upsert enabled)")
    
    logger.info(f"✅ Baseline initialization complete for {args.model_id}")
    logger.info(f"📁 Output directory: {args.output_dir}")

if __name__ == "__main__":
    main()
