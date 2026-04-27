from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg
from psycopg.rows import dict_row
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)