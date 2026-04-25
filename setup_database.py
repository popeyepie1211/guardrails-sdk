#!/usr/bin/env python
"""
setup_database.py

Initialize TimescaleDB tables for Guardrail AI.

Usage:
    python setup_database.py

Environment Variables:
    DB_USER: PostgreSQL user (default: postgres)
    DB_PASSWORD: PostgreSQL password
    DB_HOST: PostgreSQL host (default: 127.0.0.1)
    DB_PORT: PostgreSQL port (default: 5432)
    DB_NAME: PostgreSQL database (default: postgres)
"""

import os
import sys
import psycopg
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Configuration
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'postgres')

def setup_database():
    """Create tables in PostgreSQL/TimescaleDB."""
    
    logger.info(f"🚀 Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    
    try:
        conn = psycopg.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Enable TimescaleDB extension
        logger.info("📦 Creating TimescaleDB extension...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
        logger.info("✅ TimescaleDB extension ready")
        
        # Create model_vitals hypertable
        logger.info("📊 Creating model_vitals table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_vitals (
                time TIMESTAMPTZ NOT NULL,
                model_id TEXT NOT NULL,
                fairness DOUBLE PRECISION NOT NULL,
                stability DOUBLE PRECISION NOT NULL,
                security DOUBLE PRECISION NOT NULL,
                privacy DOUBLE PRECISION NOT NULL,
                transparency DOUBLE PRECISION NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('normal','warning','critical')),
                wdag_trace JSONB NOT NULL,
                metrics JSONB NOT NULL,
                batch_id TEXT,
                sample_size INTEGER NOT NULL DEFAULT 0
            );
        """)
        logger.info("✅ model_vitals table created")
        
        # Create hypertable
        logger.info("⏰ Converting to hypertable...")
        cursor.execute("""
            SELECT create_hypertable('model_vitals', 'time', if_not_exists => TRUE);
        """)
        logger.info("✅ Hypertable created")
        
        # Create indexes
        logger.info("🔍 Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_vitals_model_time
            ON model_vitals (model_id, time DESC);
        """)
        logger.info("✅ Index created")
        
        # Create model_baselines table
        logger.info("📋 Creating model_baselines table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_baselines (
                model_id TEXT PRIMARY KEY,
                baseline JSONB NOT NULL,
                metadata JSONB NOT NULL,
                version TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        logger.info("✅ model_baselines table created")
        
        # Create raw_inference_events (optional, for replay/debug)
        logger.info("📝 Creating raw_inference_events table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_inference_events (
                time TIMESTAMPTZ NOT NULL,
                model_id TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                payload JSONB NOT NULL
            );
        """)
        logger.info("✅ raw_inference_events table created")
        
        # Create hypertable for events
        logger.info("⏰ Converting events to hypertable...")
        cursor.execute("""
            SELECT create_hypertable('raw_inference_events', 'time', if_not_exists => TRUE);
        """)
        logger.info("✅ Events hypertable created")
        
        cursor.close()
        conn.close()
        
        logger.info("\n✅ ✅ ✅ Database setup complete! ✅ ✅ ✅")
        logger.info("\nTables created:")
        logger.info("  - model_vitals (hypertable)")
        logger.info("  - model_baselines")
        logger.info("  - raw_inference_events (hypertable)")
        logger.info("\nYou can now run:")
        logger.info("  - worker_auditor.py (pulls from Redis and writes to model_vitals)")
        logger.info("  - dbapi.py (serves vitals to dashboard)")
        
        return True
        
    except psycopg.Error as e:
        logger.error(f"❌ Setup failed: {e}")
        return False
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

if __name__ == "__main__":
    success = setup_database()
    sys.exit(0 if success else 1)
