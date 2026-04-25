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
import pandas as pd
import psycopg
from datetime import datetime
from typing import Dict, List, Any, Optional
import redis
from redis import Redis
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

# Core Engine Imports
from guardrail_ai.core.vitals_engine import VitalsEngine
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

VITALS_QUEUE = 'vitals_queue'
DEAD_LETTER_QUEUE = 'vitals_dead_letter'

# ============================================
# GLOBAL STATE
# ============================================
# Cache engines and graphs by model_id to avoid repeated instantiation
engine_cache: Dict[str, VitalsEngine] = {}
graph_cache: Dict[str, WDAG] = {}
executor_cache: Dict[str, WDAGExecutor] = {}


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
    Results are cached by model_id.
    """
    if model_id in engine_cache:
        logger.debug(f"[OK] Using cached engine for {model_id}")
        return engine_cache[model_id], graph_cache[model_id], executor_cache[model_id]
    
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
    
    # Cache all three
    engine_cache[model_id] = engine
    graph_cache[model_id] = graph
    executor_cache[model_id] = executor
    
    logger.info(f"[OK] Built engine and graph for {model_id}")
    return engine, graph, executor

# ============================================
# BASELINE LOADING (Temporary - from JSON)
# ============================================
def load_baseline(model_id: str) -> Dict[str, Any]:
    """
    Load baseline for a model.
    TODO: Replace with DB lookup from model_baselines table.
    For now, uses hardcoded default or JSON file.
    """
    baseline_file = f"baselines/{model_id}.json"
    
    if os.path.exists(baseline_file):
        logger.info(f"[INFO] Loading baseline from {baseline_file}")
        with open(baseline_file, 'r') as f:
            return json.load(f)
    
    # Fallback: hardcoded default
    logger.warning(f"[WARN] No baseline file found for {model_id}. Using defaults.")
    return {
        "baseline_summary": {
            "gini": {"mean": 0.45, "std": 0.05},
            "psi": {"mean": 0.02, "std": 0.01},
            "linf": {"mean": 50000, "std": 10000},
            "privacy_score": {"mean": 0.90, "std": 0.03},
            "statistical_parity": {"mean": 0.85, "std": 0.05},
            "ood_score": {"mean": 0.80, "std": 0.05},
            "shap_importance": {"mean": 0.50, "std": 0.10},
        }
    }

def load_metadata(model_id: str) -> Dict[str, Any]:
    """
    Load metadata for a model.
    TODO: Replace with DB lookup from model_baselines table.
    For now, uses JSON file.
    """
    metadata_file = f"baselines/{model_id}_metadata.json"
    
    if os.path.exists(metadata_file):
        logger.info(f"[INFO] Loading metadata from {metadata_file}")
        with open(metadata_file, 'r') as f:
            return json.load(f)
    
    # Fallback: default finance model
    logger.warning(f"[WARN] No metadata file found for {model_id}. Using defaults.")
    return {
        "domain": "finance",
        "feature_columns": ["income", "credit_score"],
        "numerical_features": ["income", "credit_score"],
        "categorical_features": ["gender"],
        "protected_attributes": {
            "type": "categorical",
            "columns": ["gender"]
        },
        "quasi_identifier_columns": ["gender"],
        "prediction_column": "prediction",
        "prediction_type": "binary"
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
        
        # 1. Load baseline and metadata
        baseline = load_baseline(model_id)
        metadata = load_metadata(model_id)
        
        # 2. Transform payload to DataFrame
        df = transform_payload_to_dataframe(payload, metadata)
        logger.debug(f"[OK] Transformed {len(df)} rows into DataFrame")
        
        # 3. Build or fetch engine and graph
        engine, graph, executor = build_engine_and_graph(model_id, baseline, metadata)
        
        # 4. Execute WDAG
        results = executor.run("Data_Stream", df)
        logger.info(f"[INFO] WDAG execution complete. Status: {results.get('status', 'unknown')}")
        
        # 5. Extract metrics and vitals
        metrics = results.get("metrics", {})
        overall_status = results.get("status", "normal")
        
        # Normalize the five vitals with fallbacks
        fairness = metrics.get("statistical_parity", {}).get("value", 0.85)
        stability = 1 - metrics.get("psi", {}).get("value", 0.08)
        security = 0.68 if overall_status != "normal" else 0.95
        privacy = metrics.get("privacy_score", {}).get("value", 0.90)
        transparency = metrics.get("gini", {}).get("value", 0.45)
        
        # Extract WDAG trace
        wdag_trace_json = json.dumps(graph.to_dict())
        metrics_json = json.dumps(metrics)
        
        # 6. Insert into TimescaleDB
        cursor = db_conn.cursor()
        
        insert_query = """
            INSERT INTO model_vitals 
            (time, model_id, fairness, stability, security, privacy, transparency, status, wdag_trace, metrics, batch_id, sample_size) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        record = (
            datetime.now(),
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
        db_conn.commit()
        cursor.close()
        
        logger.info(f"[OK] Batch {batch_id} persisted to TimescaleDB. Status: {overall_status}")
        return True
        
    except ValueError as e:
        logger.error(f"[ERROR] Validation error in batch: {e}")
        return False
    except psycopg.Error as e:
        logger.error(f"[ERROR] Database error: {e}")
        db_conn.rollback()
        return False
    except Exception as e:
        logger.error(f"[ERROR] Unexpected error processing batch {batch_id}: {e}", exc_info=True)
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
