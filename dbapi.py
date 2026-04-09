from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="Guardrails Governance API")

# Allow your React app to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Vite's default port
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
        # Use RealDictCursor to return rows as dictionaries instead of tuples
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query TimescaleDB for the single most recent entry
        query = """
            SELECT time, fairness, stability, security, privacy, transparency, status 
            FROM model_vitals 
            ORDER BY time DESC 
            LIMIT 1;
        """
        cursor.execute(query)
        result = cursor.fetchone()
        
        if not result:
            return {"status": "no_data"}
            
        # Optional: You could also run a second query here to get the last 10 rows 
        # for your Drift Time-Series chart!
            
        return dict(result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    import uvicorn
    # Runs the server on http://localhost:8000
    uvicorn.run(app, host="0.0.0.0", port=8000)