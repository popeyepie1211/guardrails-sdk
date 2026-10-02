from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
import psycopg
from psycopg.rows import dict_row
import json
import io
import os
import sys
import logging
import shutil
import tempfile
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

# ---------------------------------------------------------------------------
# Production baseline initializer — root-level module
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from baseline_initializer import (
    compute_baseline,
    build_metadata,
    save_baseline_to_db,
)

# ---------------------------------------------------------------------------
# Task-1 artifact storage
# ---------------------------------------------------------------------------
from guardrail_ai.core.artifact_storage import (
    save_model_artifact,
    save_preprocessor_artifact,
    save_background_artifact,
    get_artifact_paths,
    ArtifactStorageError,
    ArtifactValidationError,
    ArtifactSizeError,
    ArtifactPathError,
)

logger = logging.getLogger("dbapi")

# Valid enum sets (kept in sync with baseline_initializer.py CLI choices)
_VALID_DOMAINS = {"healthcare", "finance", "standard"}
_VALID_PREDICTION_TYPES = {"probability", "binary", "multiclass", "regression"}

app = FastAPI(title="Guardrails Governance API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    return psycopg.connect(
        user="postgres",
        password="password",
        host="127.0.0.1",
        port="5432",
        dbname="postgres"
    )

@app.get("/health")
def health_check():
    """Health check endpoint."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Unhealthy: {str(e)}")

@app.get("/api/vitals/latest")
def get_latest_vitals(model_id: Optional[str] = Query(None)):
    """
    Get latest vitals record.
    If model_id provided, get latest for that model.
    Otherwise, get absolute latest.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)
        
        if model_id:
            query = """
                SELECT time, model_id, fairness, stability, security, privacy, transparency, status, wdag_trace, metrics, sample_size
                FROM model_vitals 
                WHERE model_id = %s
                ORDER BY time DESC 
                LIMIT 1;
            """
            cursor.execute(query, (model_id,))
        else:
            query = """
                SELECT time, model_id, fairness, stability, security, privacy, transparency, status, wdag_trace, metrics, sample_size
                FROM model_vitals 
                ORDER BY time DESC 
                LIMIT 1;
            """
            cursor.execute(query)
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            return {"status": "no_data"}
        
        # Ensure wdag_trace and metrics are parsed JSON
        record = dict(result)
        if isinstance(record.get("wdag_trace"), str):
            try:
                record["wdag_trace"] = json.loads(record["wdag_trace"])
            except:
                pass
        if isinstance(record.get("metrics"), str):
            try:
                record["metrics"] = json.loads(record["metrics"])
            except:
                pass
        
        return record

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vitals/history")
def get_vitals_history(
    model_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    hours: int = Query(24, ge=1, le=720)
):
    """
    Get historical vitals records.
    
    Args:
        model_id: Filter by model (optional)
        limit: Number of records to return (1-1000, default 100)
        hours: Look back window in hours (1-720, default 24)
    
    Returns:
        List of vitals records ordered by time DESC
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if model_id:
            query = """
                SELECT time, model_id, fairness, stability, security, privacy, transparency, status, sample_size
                FROM model_vitals 
                WHERE model_id = %s AND time >= %s
                ORDER BY time DESC 
                LIMIT %s;
            """
            cursor.execute(query, (model_id, cutoff_time, limit))
        else:
            query = """
                SELECT time, model_id, fairness, stability, security, privacy, transparency, status, sample_size
                FROM model_vitals 
                WHERE time >= %s
                ORDER BY time DESC 
                LIMIT %s;
            """
            cursor.execute(query, (cutoff_time, limit))
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [dict(row) for row in results]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/models")
def list_models():
    """
    Get list of all models with latest status.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)
        
        query = """
            WITH all_models AS (
                SELECT model_id FROM models
                UNION
                SELECT DISTINCT model_id FROM model_vitals
            )
            SELECT
                am.model_id,
                COALESCE(m.model_name, am.model_id) AS model_name,
                COALESCE(m.domain, 'standard') AS domain,
                v.time,
                v.status,
                v.fairness,
                v.stability,
                v.security,
                v.privacy,
                v.transparency
            FROM all_models am
            LEFT JOIN models m ON m.model_id = am.model_id
            LEFT JOIN LATERAL (
                SELECT time, status, fairness, stability, security, privacy, transparency
                FROM model_vitals
                WHERE model_id = am.model_id
                ORDER BY time DESC
                LIMIT 1
            ) v ON TRUE
            ORDER BY am.model_id;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [dict(row) for row in results]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/shap/history")
def get_shap_history(
    model_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    hours: int = Query(24, ge=1, le=720),
):
    """Return SHAP top-feature history rows for trend and audit views."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)
        cutoff_time = datetime.now() - timedelta(hours=hours)

        if model_id:
            cursor.execute(
                """
                SELECT time, model_id, batch_id, feature_name, shap_value
                FROM shap_summary
                WHERE model_id = %s AND time >= %s
                ORDER BY time DESC
                LIMIT %s;
                """,
                (model_id, cutoff_time, limit),
            )
        else:
            cursor.execute(
                """
                SELECT time, model_id, batch_id, feature_name, shap_value
                FROM shap_summary
                WHERE time >= %s
                ORDER BY time DESC
                LIMIT %s;
                """,
                (cutoff_time, limit),
            )

        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/nodes/history")
def get_node_status_history(
    model_id: Optional[str] = Query(None),
    node_name: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    hours: int = Query(24, ge=1, le=720),
):
    """Return node status transitions for WDAG auditability."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)
        cutoff_time = datetime.now() - timedelta(hours=hours)

        query = """
            SELECT time, model_id, batch_id, node_name, status
            FROM node_status_history
            WHERE time >= %s
        """
        params: List[Any] = [cutoff_time]

        if model_id:
            query += " AND model_id = %s"
            params.append(model_id)
        if node_name:
            query += " AND node_name = %s"
            params.append(node_name)

        query += " ORDER BY time DESC LIMIT %s"
        params.append(limit)

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/heartbeat/latest")
def get_latest_heartbeat(model_id: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=2000)):
    """Return latest heartbeat records for liveness monitoring."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)

        if model_id:
            cursor.execute(
                """
                SELECT time, model_id, node_name, alive
                FROM heartbeat_log
                WHERE model_id = %s
                ORDER BY time DESC
                LIMIT %s;
                """,
                (model_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT time, model_id, node_name, alive
                FROM heartbeat_log
                ORDER BY time DESC
                LIMIT %s;
                """,
                (limit,),
            )

        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
def get_statistics(model_id: Optional[str] = Query(None), hours: int = Query(24)):
    """
    Get aggregate statistics for a model.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if model_id:
            query = """
                SELECT 
                    model_id,
                    COUNT(*) as total_records,
                    AVG(fairness) as avg_fairness,
                    AVG(stability) as avg_stability,
                    AVG(security) as avg_security,
                    AVG(privacy) as avg_privacy,
                    AVG(transparency) as avg_transparency,
                    SUM(sample_size) as total_samples,
                    MIN(time) as window_start,
                    MAX(time) as window_end
                FROM model_vitals 
                WHERE model_id = %s AND time >= %s
                GROUP BY model_id;
            """
            cursor.execute(query, (model_id, cutoff_time))
        else:
            query = """
                SELECT 
                    COUNT(*) as total_records,
                    AVG(fairness) as avg_fairness,
                    AVG(stability) as avg_stability,
                    AVG(security) as avg_security,
                    AVG(privacy) as avg_privacy,
                    AVG(transparency) as avg_transparency,
                    SUM(sample_size) as total_samples,
                    MIN(time) as window_start,
                    MAX(time) as window_end
                FROM model_vitals 
                WHERE time >= %s;
            """
            cursor.execute(query, (cutoff_time,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return dict(result) if result else {}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _parse_governance_jsonb(record: dict) -> dict:
    """Parse JSONB columns that psycopg may return as strings."""
    for col in ("decision_json", "report_json", "wdag_status_json", "metrics_json"):
        if isinstance(record.get(col), str):
            try:
                record[col] = json.loads(record[col])
            except (json.JSONDecodeError, TypeError):
                pass
    return record

_GOVERNANCE_COLUMNS = (
    "time, model_id, domain, environment, batch_id, "
    "diagnosis, severity, confidence, recommended_action, verdict, "
    "governance_health, decision_json, report_json, wdag_status_json, metrics_json"
)

@app.get("/api/governance/latest")
def get_latest_governance(model_id: Optional[str] = Query(None)):
    """
    Get latest governance decision record.
    If model_id provided, get latest for that model.
    Otherwise, get absolute latest.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)

        if model_id:
            query = f"""
                SELECT {_GOVERNANCE_COLUMNS}
                FROM governance_decisions
                WHERE model_id = %s
                ORDER BY time DESC
                LIMIT 1;
            """
            cursor.execute(query, (model_id,))
        else:
            query = f"""
                SELECT {_GOVERNANCE_COLUMNS}
                FROM governance_decisions
                ORDER BY time DESC
                LIMIT 1;
            """
            cursor.execute(query)

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if not result:
            if model_id:
                return {"model_id": model_id, "data": None}
            return {"status": "no_data"}

        record = _parse_governance_jsonb(dict(result))
        return record

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/governance/history")
def get_governance_history(
    model_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    hours: int = Query(24, ge=1, le=720),
):
    """
    Get historical governance decision records.

    Args:
        model_id: Filter by model (optional)
        limit: Number of records to return (1-1000, default 100)
        hours: Look back window in hours (1-720, default 24)

    Returns:
        List of governance decision records ordered by time DESC
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)

        cutoff_time = datetime.now() - timedelta(hours=hours)

        if model_id:
            query = f"""
                SELECT {_GOVERNANCE_COLUMNS}
                FROM governance_decisions
                WHERE model_id = %s AND time >= %s
                ORDER BY time DESC
                LIMIT %s;
            """
            cursor.execute(query, (model_id, cutoff_time, limit))
        else:
            query = f"""
                SELECT {_GOVERNANCE_COLUMNS}
                FROM governance_decisions
                WHERE time >= %s
                ORDER BY time DESC
                LIMIT %s;
            """
            cursor.execute(query, (cutoff_time, limit))

        results = cursor.fetchall()
        cursor.close()
        conn.close()

        return [_parse_governance_jsonb(dict(row)) for row in results]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/governance/report/latest")
def get_latest_governance_report(model_id: Optional[str] = Query(None)):
    """
    Get the full report_json for the latest governance decision for a model,
    plus time and batch_id for context.
    Returns 404 if no governance decisions exist for the given model_id.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)

        if model_id:
            query = """
                SELECT time, batch_id, report_json
                FROM governance_decisions
                WHERE model_id = %s
                ORDER BY time DESC
                LIMIT 1;
            """
            cursor.execute(query, (model_id,))
        else:
            query = """
                SELECT time, batch_id, report_json
                FROM governance_decisions
                ORDER BY time DESC
                LIMIT 1;
            """
            cursor.execute(query)

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if not result:
            detail = f"No governance decisions found for model_id '{model_id}'" if model_id else "No governance decisions found"
            raise HTTPException(status_code=404, detail=detail)

        record = dict(result)
        if isinstance(record.get("report_json"), str):
            try:
                record["report_json"] = json.loads(record["report_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        return record

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===========================================================================
# POST /api/models/register
# ===========================================================================

def _parse_json_field(raw: str, field_name: str) -> Any:
    """
    Parse a JSON string submitted as a multipart form field.
    Returns the parsed Python value.
    Raises HTTPException 422 on parse failure or if value is not the right type.
    """
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be valid JSON. Parse error: {exc}",
        )


def _require_json_list(raw: str, field_name: str) -> list:
    """Parse and validate that a form field is a non-null JSON array."""
    parsed = _parse_json_field(raw, field_name)
    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be a JSON array (e.g. [\"col1\", \"col2\"]).",
        )
    return parsed


def _cleanup_artifacts(paths: list[str]) -> None:
    """Best-effort cleanup of saved artifact files on registration failure."""
    for p in paths:
        if p and os.path.isfile(p):
            try:
                os.remove(p)
                logger.info("[CLEANUP] Removed artifact: %s", p)
            except OSError as e:
                logger.warning("[CLEANUP] Could not remove %s: %s", p, e)


@app.post("/api/models/register", status_code=201)
async def register_model(
    # ---- required identity / config fields ----
    model_id: str = Form(...),
    model_name: str = Form(...),
    domain: str = Form(...),
    prediction_type: str = Form(...),
    # ---- feature column arrays (JSON-encoded strings) ----
    feature_columns: str = Form(...),
    numerical_features: str = Form(...),
    categorical_features: str = Form(...),
    quasi_identifier_columns: str = Form(...),
    # ---- optional metadata ----
    protected_attributes: Optional[str] = Form(None),
    model_version: str = Form("v1"),
    prediction_column: str = Form("prediction"),
    # ---- file uploads ----
    model_file: UploadFile = File(...),
    historical_data_file: UploadFile = File(...),
    preprocessor_file: Optional[UploadFile] = File(None),
    shap_background_file: Optional[UploadFile] = File(None),
):
    """
    POST /api/models/register

    Register a new model for monitoring via the production baseline pipeline.

    Architecture::

        multipart/form-data
          |
          v
        dbapi.py  (this endpoint)
          |
          +--> artifact_storage.save_model_artifact()         (Task 1)
          +--> artifact_storage.save_preprocessor_artifact()  (Task 1, optional)
          +--> artifact_storage.save_background_artifact()    (Task 1, optional)
          |
          +--> baseline_initializer.build_metadata()
          +--> baseline_initializer.compute_baseline()
          +--> baseline_initializer.save_baseline_to_db()
                         |
                         v
                    PostgreSQL
                         |
                         v
                  existing worker pipeline (unchanged)

    Returns HTTP 201 on success, 409 on duplicate model_id, 422 on
    validation errors, 500 on unexpected server errors.
    """

    # -----------------------------------------------------------------------
    # 1. Basic string validation
    # -----------------------------------------------------------------------
    if not model_id or not model_id.strip():
        raise HTTPException(status_code=422, detail="model_id is required.")
    model_id = model_id.strip()

    if not model_name or not model_name.strip():
        raise HTTPException(status_code=422, detail="model_name is required.")
    model_name = model_name.strip()

    # -----------------------------------------------------------------------
    # 2. Enum validation
    # -----------------------------------------------------------------------
    if domain not in _VALID_DOMAINS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid domain {domain!r}. "
                f"Valid options are: {', '.join(sorted(_VALID_DOMAINS))}."
            ),
        )

    if prediction_type not in _VALID_PREDICTION_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid prediction_type {prediction_type!r}. "
                f"Valid options are: {', '.join(sorted(_VALID_PREDICTION_TYPES))}."
            ),
        )

    # -----------------------------------------------------------------------
    # 3. Parse JSON array fields
    # -----------------------------------------------------------------------
    feature_cols = _require_json_list(feature_columns, "feature_columns")
    num_features = _require_json_list(numerical_features, "numerical_features")
    cat_features = _require_json_list(categorical_features, "categorical_features")
    quasi_ids = _require_json_list(quasi_identifier_columns, "quasi_identifier_columns")

    if not feature_cols:
        raise HTTPException(status_code=422, detail="feature_columns must not be empty.")

    # Hard requirement: quasi_identifier_columns must be non-empty
    if not quasi_ids:
        raise HTTPException(
            status_code=422,
            detail="quasi_identifier_columns must contain at least one column.",
        )

    # -----------------------------------------------------------------------
    # 4. Parse optional protected_attributes
    # -----------------------------------------------------------------------
    parsed_protected: Optional[Dict[str, Any]] = None
    if protected_attributes:
        parsed_protected = _parse_json_field(protected_attributes, "protected_attributes")
        if not isinstance(parsed_protected, dict):
            raise HTTPException(
                status_code=422,
                detail="protected_attributes must be a JSON object.",
            )
        if "type" not in parsed_protected:
            raise HTTPException(
                status_code=422,
                detail="protected_attributes must have a 'type' field.",
            )
        if parsed_protected.get("type") not in ("categorical", "one_hot"):
            raise HTTPException(
                status_code=422,
                detail="protected_attributes.type must be 'categorical' or 'one_hot'.",
            )
        if not isinstance(parsed_protected.get("columns"), list):
            raise HTTPException(
                status_code=422,
                detail="protected_attributes.columns must be a list.",
            )

    # -----------------------------------------------------------------------
    # 5. Duplicate model_id check (transactional — prevents race conditions)
    #    Done before any expensive operations (artifact storage, baseline).
    # -----------------------------------------------------------------------
    try:
        with psycopg.connect(
            user="postgres", password="password",
            host="127.0.0.1", port="5432", dbname="postgres",
        ) as _check_conn:
            with _check_conn.cursor() as _cur:
                # Lock the row (if it exists) to guard against simultaneous
                # requests for the same model_id.
                _cur.execute(
                    "SELECT model_id FROM models WHERE model_id = %s FOR UPDATE;",
                    (model_id,),
                )
                if _cur.fetchone() is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Model {model_id!r} is already registered.",
                    )
    except HTTPException:
        raise
    except Exception as db_err:
        raise HTTPException(
            status_code=500,
            detail=f"Database connectivity error during duplicate check: {db_err}",
        )

    # -----------------------------------------------------------------------
    # 6. Read uploaded file bytes (done once each before validation)
    # -----------------------------------------------------------------------
    model_bytes = await model_file.read()
    if not model_bytes:
        raise HTTPException(status_code=422, detail="model_file is empty.")

    hist_bytes = await historical_data_file.read()
    if not hist_bytes:
        raise HTTPException(status_code=422, detail="historical_data_file is empty.")

    preprocessor_bytes: Optional[bytes] = None
    if preprocessor_file is not None:
        preprocessor_bytes = await preprocessor_file.read()
        if not preprocessor_bytes:
            preprocessor_bytes = None  # treat empty upload as not supplied

    background_bytes: Optional[bytes] = None
    if shap_background_file is not None:
        background_bytes = await shap_background_file.read()
        if not background_bytes:
            background_bytes = None

    # -----------------------------------------------------------------------
    # 7. Load and validate historical CSV before touching permanent storage
    # -----------------------------------------------------------------------
    try:
        df = pd.read_csv(io.BytesIO(hist_bytes))
    except Exception as csv_err:
        raise HTTPException(
            status_code=422,
            detail=f"historical_data_file could not be parsed as CSV: {csv_err}",
        )

    if df.empty:
        raise HTTPException(
            status_code=422,
            detail="historical_data_file is empty (zero rows after parsing).",
        )

    # Validate prediction column exists
    if prediction_column not in df.columns:
        raise HTTPException(
            status_code=422,
            detail=(
                f"historical_data_file is missing the required prediction column "
                f"{prediction_column!r}. Columns present: {list(df.columns)}."
            ),
        )

    # Validate required feature columns exist
    missing_feature_cols = [c for c in feature_cols if c not in df.columns]
    if missing_feature_cols:
        raise HTTPException(
            status_code=422,
            detail=(
                f"historical_data_file is missing required feature columns: "
                f"{missing_feature_cols}."
            ),
        )

    # Validate quasi_identifier columns exist in df
    missing_quasi = [c for c in quasi_ids if c not in df.columns]
    if missing_quasi:
        raise HTTPException(
            status_code=422,
            detail=(
                f"historical_data_file is missing quasi_identifier columns: "
                f"{missing_quasi}."
            ),
        )

    # If protected_attributes provided, validate those columns exist and
    # filter out any that are not present in this dataset (mirrors CLI behavior)
    if parsed_protected:
        pa_columns = parsed_protected.get("columns", [])
        present_pa = [c for c in pa_columns if c in df.columns]
        if not present_pa:
            # No protected columns found in df — drop protected_attributes
            logger.warning(
                "[REGISTER] protected_attributes columns %s not found in historical CSV; "
                "disabling fairness tracking.",
                pa_columns,
            )
            parsed_protected = None
        else:
            parsed_protected = dict(parsed_protected)
            parsed_protected["columns"] = present_pa

    # -----------------------------------------------------------------------
    # 8. Save artifacts via Task-1 module (validation + atomic write)
    #    Collect saved paths for cleanup on later failure.
    # -----------------------------------------------------------------------
    saved_paths: list[str] = []
    model_artifact_path: Optional[str] = None
    preprocessor_artifact_path: Optional[str] = None
    shap_background_path: Optional[str] = None

    try:
        model_artifact_path = save_model_artifact(
            model_id=model_id,
            version=model_version,
            file_bytes=model_bytes,
            filename=model_file.filename or "model.joblib",
        )
        saved_paths.append(model_artifact_path)

    except ArtifactPathError as e:
        raise HTTPException(status_code=422, detail=f"model_id/version path error: {e}")
    except ArtifactSizeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ArtifactValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"model_file is not a valid joblib/pickle file: {e}",
        )
    except ArtifactStorageError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error saving model artifact: {e}",
        )

    try:
        if preprocessor_bytes is not None:
            preprocessor_artifact_path = save_preprocessor_artifact(
                model_id=model_id,
                version=model_version,
                file_bytes=preprocessor_bytes,
                filename=preprocessor_file.filename or "preprocessor.joblib",
            )
            saved_paths.append(preprocessor_artifact_path)

        if background_bytes is not None:
            shap_background_path = save_background_artifact(
                model_id=model_id,
                version=model_version,
                file_bytes=background_bytes,
                filename=shap_background_file.filename or "background.csv",
            )
            saved_paths.append(shap_background_path)

    except (ArtifactPathError, ArtifactSizeError, ArtifactValidationError, ArtifactStorageError) as e:
        _cleanup_artifacts(saved_paths)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        _cleanup_artifacts(saved_paths)
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error saving optional artifact: {e}",
        )

    # -----------------------------------------------------------------------
    # 9. Build metadata using the production baseline_initializer function
    # -----------------------------------------------------------------------
    try:
        metadata = build_metadata(
            df=df,
            feature_columns=feature_cols,
            prediction_column=prediction_column,
            domain=domain,
            prediction_type=prediction_type,
            numerical_features=num_features,
            categorical_features=cat_features,
            protected_attributes=parsed_protected,
            quasi_identifier_columns=quasi_ids,
        )
    except Exception as e:
        _cleanup_artifacts(saved_paths)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build model metadata: {e}",
        )

    # Augment metadata with artifact paths and version
    # (mirrors what baseline_initializer.py CLI does after build_metadata())
    metadata["model_version"] = model_version
    metadata["model_name"] = model_name
    if model_artifact_path:
        metadata["model_artifact_path"] = model_artifact_path
    if preprocessor_artifact_path:
        metadata["preprocessor_artifact_path"] = preprocessor_artifact_path
    if shap_background_path:
        metadata["shap_background_path"] = shap_background_path
    metadata.setdefault("shap_explainer_type", "auto")

    # -----------------------------------------------------------------------
    # 10. Compute real baseline using the production function
    # -----------------------------------------------------------------------
    try:
        baseline = compute_baseline(df, metadata)
    except Exception as e:
        _cleanup_artifacts(saved_paths)
        raise HTTPException(
            status_code=500,
            detail=f"Baseline computation failed: {e}",
        )

    # -----------------------------------------------------------------------
    # 11. Persist to PostgreSQL (only for genuinely new models)
    #     save_baseline_to_db() uses UPSERT internally; the duplicate guard
    #     above ensures we only reach this point for new model_ids.
    # -----------------------------------------------------------------------
    try:
        save_baseline_to_db(
            model_id=model_id,
            model_name=model_name,
            domain=domain,
            version=model_version,
            baseline=baseline,
            metadata=metadata,
        )
    except Exception as e:
        _cleanup_artifacts(saved_paths)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to persist baseline to database: {e}",
        )

    # -----------------------------------------------------------------------
    # 12. Build success response
    # -----------------------------------------------------------------------
    baseline_summary = baseline.get("baseline_summary", {})
    numerical_dist = baseline.get("distributions", {}).get("numerical", {})

    return {
        "model_id": model_id,
        "status": "registered",
        "baseline_computed": True,
        "baseline_metrics": list(baseline_summary.keys()),
        "numerical_distributions_populated": bool(
            numerical_dist
            and any(len(v) > 0 for v in numerical_dist.values())
        ),
        "artifact_paths": {
            "model": model_artifact_path,
            "preprocessor": preprocessor_artifact_path,
            "shap_background": shap_background_path,
        },
        "model_version": model_version,
    }


# ===========================================================================
# GET /api/models/{model_id}/status
# ===========================================================================

@app.get("/api/models/{model_id}/status")
def get_model_status(model_id: str):
    """
    GET /api/models/{model_id}/status

    Returns whether the model is registered and ready for monitoring.

    ``distributions_available`` is True only when model_baselines contains
    real, non-empty numerical distribution data -- not merely because a row
    exists.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)

        # Fetch registration record
        cursor.execute(
            """
            SELECT
                m.model_id,
                m.model_name,
                m.domain,
                m.created_at,
                mb.version,
                mb.metadata
            FROM models m
            JOIN model_baselines mb ON mb.model_id = m.model_id
            WHERE m.model_id = %s;
            """,
            (model_id,),
        )
        row = cursor.fetchone()

        if row is None:
            # Model might exist only in models table but not baselines, or not at all
            cursor.execute(
                "SELECT model_id FROM models WHERE model_id = %s;",
                (model_id,),
            )
            if cursor.fetchone() is None:
                cursor.close()
                conn.close()
                raise HTTPException(
                    status_code=404,
                    detail=f"Model {model_id!r} is not registered.",
                )
            # Registered in models table but no baseline yet
            cursor.close()
            conn.close()
            return {
                "model_id": model_id,
                "registered": True,
                "baseline_ready": False,
                "distributions_available": False,
            }

        record = dict(row)
        raw_meta = record.get("metadata", {})
        if isinstance(raw_meta, str):
            try:
                raw_meta = json.loads(raw_meta)
            except Exception:
                raw_meta = {}

        # Check whether numerical distributions are actually populated.
        # Query the baseline JSONB column directly to inspect distributions.
        cursor.execute(
            """
            SELECT
                baseline -> 'distributions' -> 'numerical' AS numerical_dist
            FROM model_baselines
            WHERE model_id = %s;
            """,
            (model_id,),
        )
        dist_row = cursor.fetchone()
        cursor.close()
        conn.close()

        distributions_available = False
        if dist_row:
            num_dist = dist_row["numerical_dist"]
            if isinstance(num_dist, str):
                try:
                    num_dist = json.loads(num_dist)
                except Exception:
                    num_dist = {}
            if isinstance(num_dist, dict):
                distributions_available = any(
                    isinstance(v, list) and len(v) > 0
                    for v in num_dist.values()
                )

        return {
            "model_id": record["model_id"],
            "registered": True,
            "baseline_ready": True,
            "model_name": record.get("model_name"),
            "domain": record.get("domain"),
            "version": record.get("version"),
            "prediction_type": raw_meta.get("prediction_type"),
            "feature_columns": raw_meta.get("feature_columns"),
            "numerical_features": raw_meta.get("numerical_features"),
            "artifact_paths": {
                "model": raw_meta.get("model_artifact_path"),
                "preprocessor": raw_meta.get("preprocessor_artifact_path"),
                "shap_background": raw_meta.get("shap_background_path"),
            },
            "distributions_available": distributions_available,
            "registered_at": record.get("created_at"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)