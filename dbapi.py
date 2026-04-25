from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg
from psycopg.rows import dict_row
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

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
            SELECT DISTINCT ON (model_id) 
                model_id, 
                time, 
                status, 
                fairness, 
                stability, 
                security, 
                privacy, 
                transparency
            FROM model_vitals 
            ORDER BY model_id, time DESC;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [dict(row) for row in results]

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