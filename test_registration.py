import requests
import os
import time
import uuid
import json

BASE_URL = "http://localhost:8002/api/models"
INGESTION_URL = "http://localhost:3000/v1/ingest"
TEST_MODEL_ID = f"test_endpoint_model_{uuid.uuid4().hex[:8]}"
MODEL_FILE_PATH = "test_model_artifact.joblib"
DATA_FILE_PATH = "test_historical_data.csv"

def setup_files():
    # 1. Create a real sklearn model so it can be unpickled by the API server and worker
    import pickle
    import pandas as pd
    from sklearn.linear_model import LogisticRegression

    df = pd.DataFrame({
        "income": [50000, 60000, 45000, 80000, 55000],
        "credit_score": [700, 750, 650, 800, 720],
        "gender": [1, 0, 1, 0, 1], # Simplified dummy encoding for training
    })
    y = [1, 0, 1, 0, 1]
    
    model = LogisticRegression()
    model.fit(df, y)
    
    with open(MODEL_FILE_PATH, "wb") as f:
        pickle.dump(model, f)

    # 2. Create historical data CSV
    with open(DATA_FILE_PATH, "w") as f:
        f.write("income,credit_score,gender,prediction\n")
        f.write("50000,700,M,1\n")
        f.write("60000,750,F,0\n")
        f.write("45000,650,M,1\n")
        f.write("80000,800,F,0\n")
        f.write("55000,720,M,1\n")
        f.write("65000,780,F,0\n")
        f.write("40000,600,M,1\n")
        f.write("90000,820,F,0\n")
        f.write("52000,710,M,1\n")
        f.write("75000,790,F,0\n")
        f.write("48000,680,M,1\n")
        f.write("85000,810,F,0\n")
        f.write("58000,740,M,1\n")
        f.write("62000,760,F,0\n")
        f.write("42000,620,M,1\n")
        f.write("88000,830,F,0\n")
        f.write("53000,730,M,1\n")
        f.write("70000,770,F,0\n")
        f.write("46000,660,M,1\n")
        f.write("82000,805,F,0\n")


def cleanup_files():
    if os.path.exists(MODEL_FILE_PATH):
        os.remove(MODEL_FILE_PATH)
    if os.path.exists(DATA_FILE_PATH):
        os.remove(DATA_FILE_PATH)

def run_test(name, fn):
    print(f"\n[{name}] Running...")
    try:
        fn()
        print(f"[{name}] \033[92mPASS\033[0m")
    except Exception as e:
        print(f"[{name}] \033[91mFAIL\033[0m: {e}")
        raise

def test_1_registration():
    print(f"  Registering model_id: {TEST_MODEL_ID}")
    with open(MODEL_FILE_PATH, "rb") as mf, open(DATA_FILE_PATH, "rb") as df, open(DATA_FILE_PATH, "rb") as bf:
        files = {
            "model_file": (MODEL_FILE_PATH, mf, "application/octet-stream"),
            "historical_data_file": (DATA_FILE_PATH, df, "text/csv"),
            "shap_background_file": (DATA_FILE_PATH, bf, "text/csv"),
        }
        data = {
            "model_id": TEST_MODEL_ID,
            "model_name": "Test Endpoint Model",
            "domain": "finance",
            "prediction_type": "binary",
            "feature_columns": '["income", "credit_score", "gender"]',
            "numerical_features": '["income", "credit_score"]',
            "categorical_features": '["gender"]',
            "quasi_identifier_columns": '["gender"]',
            "protected_attributes": '{"type": "categorical", "columns": ["gender"]}',
        }
        resp = requests.post(f"{BASE_URL}/register", data=data, files=files)
        
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    j = resp.json()
    assert j["model_id"] == TEST_MODEL_ID
    assert j["baseline_computed"] is True
    assert "gini" in j["baseline_metrics"]
    assert j["numerical_distributions_populated"] is True
    
    # Check status endpoint
    status_resp = requests.get(f"{BASE_URL}/{TEST_MODEL_ID}/status")
    assert status_resp.status_code == 200, f"Status check failed: {status_resp.text}"
    sj = status_resp.json()
    assert sj["registered"] is True
    assert sj["distributions_available"] is True
    assert sj["domain"] == "finance"

def test_2_duplicate():
    with open(MODEL_FILE_PATH, "rb") as mf, open(DATA_FILE_PATH, "rb") as df:
        files = {
            "model_file": (MODEL_FILE_PATH, mf, "application/octet-stream"),
            "historical_data_file": (DATA_FILE_PATH, df, "text/csv"),
        }
        data = {
            "model_id": TEST_MODEL_ID,
            "model_name": "Test Endpoint Model",
            "domain": "finance",
            "prediction_type": "binary",
            "feature_columns": '["income", "credit_score", "gender"]',
            "numerical_features": '["income", "credit_score"]',
            "categorical_features": '["gender"]',
            "quasi_identifier_columns": '["gender"]',
        }
        resp = requests.post(f"{BASE_URL}/register", data=data, files=files)
    assert resp.status_code == 409, f"Expected 409 for duplicate, got {resp.status_code}: {resp.text}"

def test_3_invalid_domain():
    with open(MODEL_FILE_PATH, "rb") as mf, open(DATA_FILE_PATH, "rb") as df:
        files = {
            "model_file": (MODEL_FILE_PATH, mf, "application/octet-stream"),
            "historical_data_file": (DATA_FILE_PATH, df, "text/csv"),
        }
        data = {
            "model_id": f"invalid_{uuid.uuid4().hex[:8]}",
            "model_name": "Test",
            "domain": "invalid_domain",
            "prediction_type": "binary",
            "feature_columns": '["income", "credit_score", "gender"]',
            "numerical_features": '["income", "credit_score"]',
            "categorical_features": '["gender"]',
            "quasi_identifier_columns": '["gender"]',
        }
        resp = requests.post(f"{BASE_URL}/register", data=data, files=files)
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
    assert "Invalid domain" in resp.text

def test_4_empty_quasi():
    with open(MODEL_FILE_PATH, "rb") as mf, open(DATA_FILE_PATH, "rb") as df:
        files = {
            "model_file": (MODEL_FILE_PATH, mf, "application/octet-stream"),
            "historical_data_file": (DATA_FILE_PATH, df, "text/csv"),
        }
        data = {
            "model_id": f"invalid_{uuid.uuid4().hex[:8]}",
            "model_name": "Test",
            "domain": "finance",
            "prediction_type": "binary",
            "feature_columns": '["income", "credit_score", "gender"]',
            "numerical_features": '["income", "credit_score"]',
            "categorical_features": '["gender"]',
            "quasi_identifier_columns": '[]',
        }
        resp = requests.post(f"{BASE_URL}/register", data=data, files=files)
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
    assert "quasi_identifier_columns must contain at least one column" in resp.text


def test_5_end_to_end():
    print(f"  Sending prediction batch to ingestion server for model: {TEST_MODEL_ID}")
    
    batch_payload = {
        "modelId": TEST_MODEL_ID,
        "batchId": f"batch_{uuid.uuid4().hex[:8]}",
        "timestamp": time.time(),
        "payload": [
            {"inputFeatures": {"income": 50000, "credit_score": 700, "gender": 1}, "prediction": {"value": 1}},
            {"inputFeatures": {"income": 60000, "credit_score": 750, "gender": 0}, "prediction": {"value": 0}},
            {"inputFeatures": {"income": 45000, "credit_score": 650, "gender": 1}, "prediction": {"value": 1}},
            {"inputFeatures": {"income": 80000, "credit_score": 800, "gender": 0}, "prediction": {"value": 0}},
            {"inputFeatures": {"income": 55000, "credit_score": 720, "gender": 1}, "prediction": {"value": 1}},
            {"inputFeatures": {"income": 65000, "credit_score": 780, "gender": 0}, "prediction": {"value": 0}},
            {"inputFeatures": {"income": 40000, "credit_score": 600, "gender": 1}, "prediction": {"value": 1}},
            {"inputFeatures": {"income": 90000, "credit_score": 820, "gender": 0}, "prediction": {"value": 0}},
            {"inputFeatures": {"income": 52000, "credit_score": 710, "gender": 1}, "prediction": {"value": 1}},
            {"inputFeatures": {"income": 75000, "credit_score": 790, "gender": 0}, "prediction": {"value": 0}},
        ]
    }
    
    resp = requests.post(INGESTION_URL, json=batch_payload)
    assert resp.status_code in (200, 201, 202), f"Ingestion failed: {resp.status_code} {resp.text}"
    print(f"  Ingestion queued. Wait 5s for worker auditor...")
    time.sleep(5)
    
    # Check if a vitals record was created
    vitals_resp = requests.get(f"http://localhost:8002/api/vitals/latest?model_id={TEST_MODEL_ID}")
    assert vitals_resp.status_code == 200, "Vitals check failed"
    v_j = vitals_resp.json()
    assert v_j.get("model_id") == TEST_MODEL_ID, f"No model_vitals row found for {TEST_MODEL_ID}. Full response: {v_j}"
    print(f"  [PASS] Vitals computed: Fairness={v_j.get('fairness')}, Status={v_j.get('status')}")
    
    # Check governance decisions (Digital Judge output)
    gov_resp = requests.get(f"http://localhost:8002/api/governance/latest?model_id={TEST_MODEL_ID}")
    assert gov_resp.status_code == 200, "Governance check failed"
    g_j = gov_resp.json()
    
    # g_j might have {"model_id": "...", "data": None} if missing. It should have real data if it ran.
    assert g_j.get("model_id") == TEST_MODEL_ID
    assert "verdict" in g_j or "data" not in g_j, f"No real governance decision yet. Full response: {g_j}"
    if "verdict" in g_j:
        print(f"  [PASS] Governance decision logged: Verdict={g_j['verdict']}")
    else:
        print("  [WARN] Governance decision not found yet (maybe worker still processing/WDAG node not finished).")


if __name__ == "__main__":
    setup_files()
    try:
        run_test("Test 1: Registration", test_1_registration)
        run_test("Test 2: Duplicate", test_2_duplicate)
        run_test("Test 3: Invalid Domain", test_3_invalid_domain)
        run_test("Test 4: Empty Quasi", test_4_empty_quasi)
        run_test("Test 5: E2E Pipeline", test_5_end_to_end)
    finally:
        cleanup_files()
        print("\nAll done.")
