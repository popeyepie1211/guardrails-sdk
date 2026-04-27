"""
worker_auditor.py

Continuous Python Worker (Auditor) for Guardrail AI.
- Pulls batches from Redis vitals_queue
- Transforms ingestion payloads to DataFrame
- Runs VitalsEngine + WDAG executor
- Persists results to TimescaleDB
- Implements resilience with error handling and dead-letter queues

Usage:
    python worker_auditor.py
    
Environment Variables:
    REDIS_URL: Redis connection string (default: redis://localhost:6379)
    DB_USER: PostgreSQL user (default: postgres)
    DB_PASSWORD: PostgreSQL password
    DB_HOST: PostgreSQL host (default: 127.0.0.1)
    DB_PORT: PostgreSQL port (default: 5432)
    DB_NAME: PostgreSQL database (default: postgres)
    WORKER_TIMEOUT: Read timeout in seconds (default: 30)
    BATCH_SIZE_LIMIT: Max items to process per batch (default: 1000)
"""

import json
import os
import logging
import sys
import pickle
import pandas as pd
import psycopg
from psycopg.rows import dict_row
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
import redis
from redis import Redis
import time
import numpy as np
import shap

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

# Core Engine Imports
from guardrail_ai.core.vitals_engine import VitalsEngine
from guardrail_ai.core.validator import Validator
from guardrail_ai.wdag.node import Node
from guardrail_ai.wdag.graph import WDAG
from guardrail_ai.wdag.executor import WDAGExecutor

# ============================================
# LOGGING SETUP
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('worker_auditor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION
# ============================================
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'postgres')
WORKER_TIMEOUT = int(os.getenv('WORKER_TIMEOUT', '30'))
BATCH_SIZE_LIMIT = int(os.getenv('BATCH_SIZE_LIMIT', '1000'))
STORE_RAW_EVENTS = os.getenv('STORE_RAW_EVENTS', 'false').strip().lower() in {'1', 'true', 'yes', 'on'}

VITALS_QUEUE = 'vitals_queue'
DEAD_LETTER_QUEUE = 'vitals_dead_letter'

# ============================================
# GLOBAL STATE
# ============================================
# Cache real model artifacts and SHAP explainers by model_id + version.
model_bundle_cache: Dict[str, Dict[str, Any]] = {}
shap_validation_cache: Dict[str, bool] = {}


def to_snake_case(name: str) -> str:
    result = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def to_camel_case(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def resolve_feature_value(features: Dict[str, Any], feature_name: str) -> Any:
    candidates = [
        feature_name,
        to_snake_case(feature_name),
        to_camel_case(feature_name),
        feature_name.lower(),
    ]
    for candidate in candidates:
        if candidate in features:
            return features[candidate]
    return None


def extract_prediction_value(item: Dict[str, Any]) -> Any:
    prediction = item.get("prediction")
    if isinstance(prediction, dict):
        if "value" in prediction:
            return prediction["value"]
        for key in ["score", "probability", "confidence", "prediction"]:
            if key in prediction and isinstance(prediction[key], (int, float)):
                return prediction[key]

    if "output" in item:
        output = item["output"]
        if isinstance(output, (int, float, bool)):
            return int(output) if isinstance(output, bool) else output
        if isinstance(output, dict):
            for key in ["value", "prediction", "score", "probability", "confidence"]:
                if key in output and isinstance(output[key], (int, float)):
                    return output[key]
            status = output.get("status") or output.get("label")
            if isinstance(status, str):
                normalized = status.strip().lower()
                if normalized in {"approved", "accept", "accepted", "yes", "true", "positive", "allow"}:
                    return 1
                if normalized in {"rejected", "reject", "denied", "no", "false", "negative", "block"}:
                    return 0
    return None

# ============================================
# DATABASE CONNECTION
# ============================================
def get_db_connection():
    """Create a new PostgreSQL connection."""
    try:
        conn = psycopg.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME
        )
        return conn
    except Exception as e:
        logger.error(f"[ERROR] Failed to connect to database: {e}")
        raise

# ============================================
# PAYLOAD TRANSFORMATION
# ============================================
def transform_payload_to_dataframe(
    payload: List[Dict[str, Any]],
    metadata: Dict[str, Any]
) -> pd.DataFrame:
    """
    Convert SDK ingestion payload into DataFrame for VitalsEngine.
    
    Expected payload item schema:
        {
            "eventId": "...",
            "modelId": "...",
            "timestamp": "...",
            "latencyMs": 123.45,
            "inputFeatures": {...},
            "prediction": {"value": 1, "label": "...", "confidence": 0.98, "type": "binary"},
            "metadata": {...}
        }
    
    Returns DataFrame with columns: feature_columns + prediction_column
    """
    rows = []
    
    prediction_column = metadata.get("prediction_column", "prediction")

    for item in payload:
        try:
            row = {}

            # Extract input features (normalized schema first, then legacy schema)
            features = {}
            if isinstance(item.get("inputFeatures"), dict):
                features = item["inputFeatures"]
            elif isinstance(item.get("input"), dict):
                features = item["input"]

            row.update(features)

            # Normalize required feature keys to metadata names.
            for feature_name in metadata.get("feature_columns", []):
                if feature_name not in row:
                    resolved = resolve_feature_value(features, feature_name)
                    if resolved is not None:
                        row[feature_name] = resolved

            # Extract prediction value from normalized or legacy payload.
            prediction_value = extract_prediction_value(item)
            if prediction_value is not None:
                row[prediction_column] = prediction_value
            
            rows.append(row)
        except Exception as e:
            logger.warning(f"[WARN] Failed to transform event: {e}. Skipping item.")
            continue
    
    if not rows:
        raise ValueError("No valid rows transformed from payload")
    
    df = pd.DataFrame(rows)
    
    # Ensure all required columns exist
    required_cols = metadata.get("feature_columns", []) + [metadata.get("prediction_column", "prediction")]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in transformed data: {missing_cols}")
    
    return df

# ============================================
# ENGINE & GRAPH FACTORY
# ============================================
def build_engine_and_graph(
    model_id: str,
    baseline: Dict[str, Any],
    metadata: Dict[str, Any]
) -> tuple:
    """
    Build VitalsEngine and WDAG graph for a model.
    Engine is intentionally created per batch because metadata contains
    batch-scoped SHAP values and summaries.
    """
    # Create engine
    engine = VitalsEngine(baseline=baseline, metadata=metadata)
    
    # Create WDAG graph
    graph = WDAG()
    data_node = Node("Data_Stream", "Data Engineer")
    intercept_node = Node("SDK_Intercept", "Middleware")
    vitals_node = Node("Vitals_Engine", "Analysis")
    
    graph.add_node(data_node)
    graph.add_node(intercept_node)
    graph.add_node(vitals_node)
    
    graph.add_edge("Data_Stream", "SDK_Intercept", weight=1.0)
    graph.add_edge("SDK_Intercept", "Vitals_Engine", weight=1.0)
    
    # Create executor
    executor = WDAGExecutor(graph, engine)

    logger.debug(f"[OK] Built engine and graph for {model_id}")
    return engine, graph, executor


def _artifact_cache_key(model_id: str, metadata: Dict[str, Any]) -> str:
    version = str(metadata.get("model_version", "latest"))
    return f"{model_id}:{version}"


def validate_shap_runtime_config(model_id: str, metadata: Dict[str, Any]) -> None:
    """
    One-time runtime smoke check for SHAP config and artifacts per model version.
    Fails fast with clear messages to prevent silent explainability drift.
    """
    cache_key = _artifact_cache_key(model_id, metadata)
    if shap_validation_cache.get(cache_key):
        return

    Validator.validate_shap_metadata(metadata)

    model_path = metadata.get("model_artifact_path")
    if not os.path.exists(model_path):
        raise ValueError(f"model_artifact_path not found: {model_path}")

    preprocessor_path = metadata.get("preprocessor_artifact_path")
    if preprocessor_path and not os.path.exists(preprocessor_path):
        raise ValueError(f"preprocessor_artifact_path not found: {preprocessor_path}")

    background_path = metadata.get("shap_background_path")
    if background_path and not os.path.exists(background_path):
        raise ValueError(f"shap_background_path not found: {background_path}")

    shap_validation_cache[cache_key] = True
    logger.info(f"[OK] SHAP runtime config validated for {cache_key}")


def _load_artifact(path: str) -> Any:
    if not path:
        raise ValueError("Artifact path is empty")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Artifact not found at {path}")

    # Try joblib first, then fallback to pickle for generic serialized objects.
    try:
        import joblib
        return joblib.load(path)
    except Exception:
        with open(path, "rb") as f:
            return pickle.load(f)


def _prepare_feature_frame(df: pd.DataFrame, metadata: Dict[str, Any]) -> pd.DataFrame:
    feature_order = metadata.get("feature_order") or metadata.get("feature_columns") or []
    if not feature_order:
        raise ValueError("metadata.feature_columns or metadata.feature_order is required for SHAP")

    missing = [col for col in feature_order if col not in df.columns]
    if missing:
        raise ValueError(f"Missing SHAP feature columns: {missing}")

    return df[feature_order].copy()


def _load_background_frame(feature_cols: List[str], metadata: Dict[str, Any]) -> pd.DataFrame:
    bg_path = metadata.get("shap_background_path")
    bg_rows = int(metadata.get("shap_background_rows", 200))

    if bg_path:
        if not os.path.exists(bg_path):
            raise FileNotFoundError(f"shap_background_path not found: {bg_path}")
        bg_df = pd.read_csv(bg_path)
        missing = [col for col in feature_cols if col not in bg_df.columns]
        if missing:
            raise ValueError(f"Background data missing required columns: {missing}")
        return bg_df[feature_cols].head(bg_rows)

    # Fall back to static samples in metadata if provided.
    samples = metadata.get("shap_background_samples")
    if isinstance(samples, list) and samples:
        bg_df = pd.DataFrame(samples)
        missing = [col for col in feature_cols if col not in bg_df.columns]
        if missing:
            raise ValueError(f"shap_background_samples missing required columns: {missing}")
        return bg_df[feature_cols].head(bg_rows)

    raise ValueError("SHAP requires shap_background_path or shap_background_samples in metadata")


def _build_prediction_function(
    model: Any,
    preprocessor: Optional[Any],
    feature_cols: List[str],
    expect_2d_output: bool = False,
) -> Callable[[np.ndarray], np.ndarray]:
    def _predict_internal(raw_array: np.ndarray) -> np.ndarray:
        frame = pd.DataFrame(raw_array, columns=feature_cols)
        transformed = preprocessor.transform(frame) if preprocessor is not None else frame.values

        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(transformed)
            if getattr(proba, "ndim", 1) == 2 and proba.shape[1] > 1:
                out = proba[:, 1]
            else:
                out = np.ravel(proba)
        elif hasattr(model, "decision_function"):
            out = model.decision_function(transformed)
        else:
            out = model.predict(transformed)

        out = np.asarray(out)
        if expect_2d_output and out.ndim == 1:
            return out.reshape(-1, 1)
        return out

    return _predict_internal


def _get_model_bundle(model_id: str, metadata: Dict[str, Any], feature_cols: List[str]) -> Dict[str, Any]:
    cache_key = _artifact_cache_key(model_id, metadata)
    if cache_key in model_bundle_cache:
        return model_bundle_cache[cache_key]

    model_path = metadata.get("model_artifact_path")
    if not model_path:
        raise ValueError("metadata.model_artifact_path is required for production SHAP")

    preprocessor_path = metadata.get("preprocessor_artifact_path")
    explainer_type = str(metadata.get("shap_explainer_type", "auto")).lower()

    model = _load_artifact(model_path)
    preprocessor = _load_artifact(preprocessor_path) if preprocessor_path else None

    background_df = _load_background_frame(feature_cols, metadata)
    background_array = background_df.values
    transformed_background = (
        preprocessor.transform(background_df) if preprocessor is not None else background_array
    )

    predict_fn = _build_prediction_function(model, preprocessor, feature_cols)

    if explainer_type == "tree":
        explainer = shap.TreeExplainer(model, data=transformed_background)
    elif explainer_type == "linear":
        explainer = shap.LinearExplainer(model, transformed_background)
    elif explainer_type == "kernel":
        explainer = shap.KernelExplainer(predict_fn, background_array)
    else:
        explainer = shap.Explainer(predict_fn, background_array)

    bundle = {
        "cache_key": cache_key,
        "model": model,
        "preprocessor": preprocessor,
        "predict_fn": predict_fn,
        "explainer": explainer,
        "feature_cols": feature_cols,
        "model_version": str(metadata.get("model_version", "latest")),
        "explainer_type": explainer_type,
    }
    model_bundle_cache[cache_key] = bundle
    logger.info(f"[OK] Loaded model artifact and SHAP explainer for {cache_key}")
    return bundle

# ============================================
# MODEL CONFIG LOADING (DB-backed)
# ============================================
def _normalize_json_field(value: Any, field_name: str) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError(f"{field_name} must be a JSON object")


def load_model_config(db_conn: psycopg.Connection, model_id: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load baseline and metadata for a model from the model_baselines table.
    This is the production source of truth for worker configuration.
    """
    with db_conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                b.baseline,
                b.metadata,
                b.version,
                m.model_name,
                m.domain AS model_domain
            FROM model_baselines b
            LEFT JOIN models m ON m.model_id = b.model_id
            WHERE b.model_id = %s
            LIMIT 1;
            """,
            (model_id,),
        )
        row = cursor.fetchone()

    if not row:
        raise ValueError(
            f"No baseline metadata found for model '{model_id}'. "
            "Register the model in model_baselines before starting the worker."
        )

    baseline = _normalize_json_field(row["baseline"], "baseline")
    metadata = _normalize_json_field(row["metadata"], "metadata")

    version = row.get("version")
    if version:
        metadata["model_version"] = str(version)

    if row.get("model_name") and not metadata.get("model_name"):
        metadata["model_name"] = row["model_name"]

    if row.get("model_domain") and not metadata.get("domain"):
        metadata["domain"] = row["model_domain"]

    return baseline, metadata


def enrich_metadata_from_batch(metadata: Dict[str, Any], batch: Dict[str, Any]) -> Dict[str, Any]:
    """Merge runtime envelope metadata without overriding DB-required config."""
    result = dict(metadata)
    batch_meta = batch.get("metadata") if isinstance(batch.get("metadata"), dict) else {}
    payload = batch.get("payload") if isinstance(batch.get("payload"), list) else []
    event_meta = payload[0].get("metadata") if payload and isinstance(payload[0], dict) and isinstance(payload[0].get("metadata"), dict) else {}

    merged = {
        **batch_meta,
        **event_meta,
    }

    if isinstance(merged.get("domain"), str) and merged["domain"].strip():
        result.setdefault("domain", merged["domain"].strip())

    if isinstance(merged.get("prediction_type"), str) and merged["prediction_type"].strip():
        result.setdefault("prediction_type", merged["prediction_type"].strip())

    if isinstance(merged.get("model_version"), str) and merged["model_version"].strip():
        result.setdefault("model_version", merged["model_version"].strip())

    if isinstance(merged.get("node_name"), str) and merged["node_name"].strip():
        result["node_name"] = merged["node_name"].strip()

    return result


def upsert_model_registry(cursor: psycopg.Cursor, model_id: str, metadata: Dict[str, Any]) -> None:
    model_name = str(metadata.get("model_name") or model_id)
    domain = str(metadata.get("domain") or "standard")
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


def persist_shap_summary(
    cursor: psycopg.Cursor,
    event_time: datetime,
    model_id: str,
    batch_id: str,
    metrics: Dict[str, Any],
) -> None:
    top_features = metrics.get("shap_top_features")
    if not isinstance(top_features, list) or not top_features:
        return

    records = []
    for item in top_features[:5]:
        name = item.get("name") if isinstance(item, dict) else None
        weight = item.get("weight") if isinstance(item, dict) else None
        if isinstance(name, str) and name and isinstance(weight, (int, float)):
            records.append((event_time, model_id, batch_id, name, float(weight)))

    if records:
        cursor.executemany(
            """
            INSERT INTO shap_summary (time, model_id, batch_id, feature_name, shap_value)
            VALUES (%s, %s, %s, %s, %s);
            """,
            records,
        )


def persist_node_status_history(
    cursor: psycopg.Cursor,
    event_time: datetime,
    model_id: str,
    batch_id: str,
    wdag_trace: Dict[str, Any],
) -> None:
    records = []
    for node in wdag_trace.values():
        if not isinstance(node, dict):
            continue
        node_name = node.get("name")
        status = node.get("status")
        if isinstance(node_name, str) and isinstance(status, str):
            records.append((event_time, model_id, batch_id, node_name, status))

    if records:
        cursor.executemany(
            """
            INSERT INTO node_status_history (time, model_id, batch_id, node_name, status)
            VALUES (%s, %s, %s, %s, %s);
            """,
            records,
        )


def persist_heartbeat_log(
    cursor: psycopg.Cursor,
    event_time: datetime,
    model_id: str,
    wdag_trace: Dict[str, Any],
) -> None:
    records = []
    for node in wdag_trace.values():
        if not isinstance(node, dict):
            continue
        node_name = node.get("name")
        status = node.get("status")
        if isinstance(node_name, str):
            alive = str(status).lower() != "grey"
            records.append((event_time, model_id, node_name, alive))

    if records:
        cursor.executemany(
            """
            INSERT INTO heartbeat_log (time, model_id, node_name, alive)
            VALUES (%s, %s, %s, %s);
            """,
            records,
        )

# ============================================
# SHAP COMPUTATION
# ============================================
def compute_shap_for_batch(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    model_id: str
) -> Dict[str, Any]:
    """
    Compute SHAP values using the real production model artifact.
    Returns batch scalar score, per-feature summary, and raw values for engine usage.
    """
    feature_cols = metadata.get("feature_order") or metadata.get("feature_columns") or []
    if not feature_cols:
        return {
            "available": False,
            "reason": "missing_feature_columns",
            "shap_values": None,
            "score": 0.0,
            "feature_importance": {},
            "top_features": [],
            "model_version": str(metadata.get("model_version", "unknown")),
            "explainer_type": str(metadata.get("shap_explainer_type", "unknown")),
        }

    try:
        X_df = _prepare_feature_frame(df, metadata)
        bundle = _get_model_bundle(model_id, metadata, feature_cols)
        explainer = bundle["explainer"]
        predict_fn = bundle["predict_fn"]
        explainer_type = bundle["explainer_type"]

        if explainer_type == "tree" and bundle.get("preprocessor") is not None:
            X_eval = bundle["preprocessor"].transform(X_df)
            raw_shap = explainer.shap_values(X_eval)
        elif explainer_type == "tree":
            raw_shap = explainer.shap_values(X_df.values)
        elif explainer_type == "linear":
            X_eval = bundle["preprocessor"].transform(X_df) if bundle.get("preprocessor") is not None else X_df.values
            raw_shap = explainer.shap_values(X_eval)
        elif explainer_type == "kernel":
            raw_shap = explainer.shap_values(X_df.values)
        else:
            raw_shap = explainer(X_df.values)
            raw_shap = raw_shap.values if hasattr(raw_shap, "values") else raw_shap

        if isinstance(raw_shap, list):
            shap_values = np.mean([np.abs(np.asarray(v)) for v in raw_shap], axis=0)
        else:
            shap_values = np.abs(np.asarray(raw_shap))

        if shap_values.ndim == 1:
            shap_values = shap_values.reshape(-1, 1)

        mean_abs = np.mean(shap_values, axis=0)
        importance_map = {
            feature_cols[i]: float(mean_abs[i])
            for i in range(min(len(feature_cols), len(mean_abs)))
        }
        top_features = [
            {"name": name, "weight": weight}
            for name, weight in sorted(importance_map.items(), key=lambda item: item[1], reverse=True)[:5]
        ]

        score = float(np.mean(list(importance_map.values()))) if importance_map else 0.0
        logger.info(
            f"[OK] Computed SHAP from real model for {model_id} "
            f"(version={bundle['model_version']}, features={len(importance_map)})"
        )

        return {
            "available": True,
            "reason": "ok",
            "shap_values": shap_values,
            "score": score,
            "feature_importance": importance_map,
            "top_features": top_features,
            "model_version": bundle["model_version"],
            "explainer_type": bundle["explainer_type"],
        }

    except Exception as e:
        logger.error(f"[ERROR] SHAP computation unavailable for {model_id}: {e}")
        return {
            "available": False,
            "reason": str(e),
            "shap_values": None,
            "score": 0.0,
            "feature_importance": {},
            "top_features": [],
            "model_version": str(metadata.get("model_version", "unknown")),
            "explainer_type": str(metadata.get("shap_explainer_type", "unknown")),
        }

# ============================================
# BATCH PROCESSING
# ============================================
def process_batch(
    batch: Dict[str, Any],
    redis_client: Redis,
    db_conn: psycopg.Connection
) -> bool:
    """
    Process one batch from Redis.
    Returns True if successful, False otherwise.
    """
    try:
        batch_id = batch.get("batchId", "unknown")
        model_id = batch.get("modelId", "unknown")
        payload = batch.get("payload", [])
        
        if not payload:
            logger.warning(f"[WARN] Empty payload in batch {batch_id}")
            return True  # Not an error, just empty
        
        logger.info(f"[INFO] Processing batch {batch_id} (Model: {model_id}, Items: {len(payload)})")
        
        # 1. Load baseline and metadata from DB source of truth
        baseline, metadata = load_model_config(db_conn, model_id)
        metadata = enrich_metadata_from_batch(metadata, batch)

        # 1.5 SHAP smoke validation (one-time per model version)
        validate_shap_runtime_config(model_id, metadata)
        
        # 2. Transform payload to DataFrame
        df = transform_payload_to_dataframe(payload, metadata)
        logger.debug(f"[OK] Transformed {len(df)} rows into DataFrame")
        
        # 2.5. COMPUTE SHAP FROM REAL MODEL ARTIFACT
        shap_result = compute_shap_for_batch(df, metadata, model_id)
        metadata_with_shap = dict(metadata)
        metadata_with_shap["shap_values"] = shap_result.get("shap_values")
        
        # 3. Build or fetch engine and graph
        engine, graph, executor = build_engine_and_graph(model_id, baseline, metadata_with_shap)
        
        # 4. Execute WDAG
        results = executor.run("Data_Stream", df)
        logger.info(f"[INFO] WDAG execution complete. Status: {results.get('status', 'unknown')}")
        
        # 5. Extract metrics and vitals
        metrics = results.get("metrics", {})
        overall_status = results.get("status", "normal")

        # Attach structured SHAP details for API/dashboard consumption.
        metrics["shap_feature_importance"] = shap_result.get("feature_importance", {})
        metrics["shap_top_features"] = shap_result.get("top_features", [])
        metrics["shap_status"] = {
            "available": shap_result.get("available", False),
            "reason": shap_result.get("reason", "unknown"),
            "model_version": shap_result.get("model_version", "unknown"),
            "explainer_type": shap_result.get("explainer_type", "unknown"),
        }
        
        # Normalize the five vitals with fallbacks
        fairness = metrics.get("statistical_parity", {}).get("value", 0.85)
        stability = 1 - metrics.get("psi", {}).get("value", 0.08)
        security = 0.68 if overall_status != "normal" else 0.95
        privacy = metrics.get("privacy_score", {}).get("value", 0.90)
        transparency = metrics.get("shap_importance", {}).get("value", 0.45)
        
        # Extract WDAG trace
        wdag_trace_dict = graph.to_dict()
        wdag_trace_json = json.dumps(wdag_trace_dict)
        metrics_json = json.dumps(metrics)

        event_time = datetime.now()

        # 6. Insert into TimescaleDB
        cursor = db_conn.cursor()
        upsert_model_registry(cursor, model_id, metadata)
        
        insert_query = """
            INSERT INTO model_vitals 
            (time, model_id, fairness, stability, security, privacy, transparency, status, wdag_trace, metrics, batch_id, sample_size) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        record = (
            event_time,
            model_id,
            float(fairness),
            float(stability),
            float(security),
            float(privacy),
            float(transparency),
            overall_status,
            wdag_trace_json,
            metrics_json,
            batch_id,
            len(df)
        )
        
        cursor.execute(insert_query, record)

        persist_shap_summary(cursor, event_time, model_id, batch_id, metrics)
        persist_node_status_history(cursor, event_time, model_id, batch_id, wdag_trace_dict)
        persist_heartbeat_log(cursor, event_time, model_id, wdag_trace_dict)

        if STORE_RAW_EVENTS:
            cursor.execute(
                """
                INSERT INTO raw_inference_events (time, model_id, batch_id, payload)
                VALUES (%s, %s, %s, %s);
                """,
                (event_time, model_id, batch_id, json.dumps(payload)),
            )

        db_conn.commit()
        cursor.close()
        
        logger.info(f"[OK] Batch {batch_id} persisted to TimescaleDB. Status: {overall_status}")
        return True
        
    except ValueError as e:
        logger.error(f"[ERROR] Validation error in batch: {e}")
        db_conn.rollback()
        return False
    except psycopg.Error as e:
        logger.error(f"[ERROR] Database error: {e}")
        db_conn.rollback()
        return False
    except Exception as e:
        logger.error(f"[ERROR] Unexpected error processing batch {batch_id}: {e}", exc_info=True)
        db_conn.rollback()
        return False

# ============================================
# MAIN WORKER LOOP
# ============================================
def main():
    """
    Main worker loop:
    1. Connect to Redis
    2. Connect to PostgreSQL
    3. Continuously pull from vitals_queue
    4. Process and persist
    5. Handle errors gracefully
    """
    logger.info("[START] Worker Auditor starting...")
    
    # Connect to Redis
    try:
        redis_client = redis.from_url(REDIS_URL)
        redis_client.ping()
        logger.info(f"[OK] Connected to Redis: {REDIS_URL}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to connect to Redis: {e}")
        sys.exit(1)
    
    # Connect to PostgreSQL
    try:
        db_conn = get_db_connection()
        logger.info(f"[OK] Connected to PostgreSQL: {DB_HOST}:{DB_PORT}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to connect to PostgreSQL: {e}")
        sys.exit(1)
    
    # Main loop
    iteration = 0
    empty_iterations = 0
    
    while True:
        try:
            iteration += 1
            
            # BRPOP with timeout (blocking read from right side of list)
            result = redis_client.brpop(VITALS_QUEUE, timeout=WORKER_TIMEOUT)
            
            if result is None:
                empty_iterations += 1
                if empty_iterations % 10 == 0:
                    logger.debug(f"[WAIT] Queue empty. Waiting... (iteration {iteration})")
                continue
            
            empty_iterations = 0
            queue_name, batch_json = result
            
            # Parse batch
            try:
                batch = json.loads(batch_json)
            except json.JSONDecodeError as e:
                logger.error(f"[ERROR] Failed to parse batch JSON: {e}")
                # Send to dead-letter queue
                redis_client.lpush(DEAD_LETTER_QUEUE, batch_json)
                continue
            
            # Process batch
            success = process_batch(batch, redis_client, db_conn)
            
            if not success:
                logger.warning(f"[WARN] Batch processing failed. Sending to dead-letter queue.")
                redis_client.lpush(DEAD_LETTER_QUEUE, batch_json)
        
        except KeyboardInterrupt:
            logger.info("\n[STOP] Received SIGINT. Shutting down gracefully...")
            break
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error in main loop: {e}", exc_info=True)
            time.sleep(5)  # Back off before retry
            continue
    
    # Cleanup
    try:
        db_conn.close()
        redis_client.close()
        logger.info("[OK] Worker shut down gracefully")
    except Exception as e:
        logger.error(f"[WARN] Error during shutdown: {e}")

if __name__ == "__main__":
    main()
