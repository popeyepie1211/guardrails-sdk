from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="Guardrails Governance API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    return psycopg2.connect(
        user="postgres",
        password="password",
        host="127.0.0.1",
        port="5432",
        database="postgres"
    )

@app.get("/api/vitals/latest")
def get_latest_vitals():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        
        query = """
            SELECT time, fairness, stability, security, privacy, transparency, status, wdag_trace 
            FROM model_vitals 
            ORDER BY time DESC 
            LIMIT 1;
        """
        cursor.execute(query)
        result = cursor.fetchone()
        
        if not result:
            return {"status": "no_data"}
            
        return dict(result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)