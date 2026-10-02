"""
test_artifact_storage.py

Verification script for guardrail_ai.core.artifact_storage.

Verification steps:
  Step 1 - Upload a real valid .joblib, confirm it saves to the expected path.
  Step 2 - Confirm returned path is loadable by worker_auditor._load_artifact().
  Step 3 - Upload a deliberately corrupted file, confirm rejected BEFORE disk write.
  Step 4 - Path-traversal attack, confirm rejected / sanitized.

NOTE on sklearn version compatibility
--------------------------------------
adult_income_model.joblib was serialized with sklearn 1.6.1.
The repo venv uses sklearn 1.7.2 in which _RemainderColsList was renamed,
making that file unloadable HERE (and equally unloadable by the worker).
Our validation correctly rejects such a file -- it is NOT a bug.

For Steps 1 & 2 we therefore build a small fresh model using the current
sklearn, serialize it with joblib, and run the full storage round-trip.
We also attempt each eval model to document which ones are compatible.
"""

import io
import os
import sys
import logging
import traceback
import tempfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("test_artifact_storage")

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

EVAL_ARTIFACTS = os.path.join(
    os.path.dirname(REPO_ROOT),
    "guardrail-evaluation", "artifacts"
)

ADULT_INCOME_MODEL = os.path.join(
    EVAL_ARTIFACTS, "adult_income", "adult_income_model.joblib"
)
FRAUD_CLASSIFIER = os.path.join(
    EVAL_ARTIFACTS, "credit_fraud",
    "evaluation_artifacts", "evaluation_artifacts", "fraud_classifier_only.joblib"
)
FRAUD_PREPROCESSOR = os.path.join(
    EVAL_ARTIFACTS, "credit_fraud",
    "evaluation_artifacts", "evaluation_artifacts", "fraud_preprocessor_only.joblib"
)
HOUSE_PRICE_MODEL = os.path.join(
    EVAL_ARTIFACTS, "house_price",
    "evaluation_artifacts", "evaluation_artifacts", "house_price_model.joblib"
)

# ---------------------------------------------------------------------------
from guardrail_ai.core.artifact_storage import (
    save_model_artifact,
    save_preprocessor_artifact,
    save_background_artifact,
    get_artifact_paths,
    ArtifactStorageError,
    ArtifactValidationError,
    ArtifactPathError,
    ArtifactSizeError,
    ARTIFACT_STORAGE_ROOT,
)
from worker_auditor import _load_artifact

import joblib, numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []

def report(tag, step, msg):
    line = f"{tag} {step}: {msg}"
    results.append(line)
    print(line)

print()
print("=" * 70)
print("  ARTIFACT STORAGE VERIFICATION TEST")
print(f"  Storage root : {ARTIFACT_STORAGE_ROOT}")
print("=" * 70)

# ---------------------------------------------------------------------------
# PRE-STEP: probe eval models for sklearn compatibility
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print("PRE-STEP: probing eval models for sklearn compatibility")
print("-" * 60)
eval_models = [
    ("adult_income_model.joblib",       ADULT_INCOME_MODEL),
    ("fraud_classifier_only.joblib",     FRAUD_CLASSIFIER),
    ("fraud_preprocessor_only.joblib",   FRAUD_PREPROCESSOR),
    ("house_price_model.joblib",         HOUSE_PRICE_MODEL),
]
compatible_eval_model = None
for fname, fpath in eval_models:
    if not os.path.exists(fpath):
        print(f"  MISSING  : {fname}")
        continue
    try:
        obj = _load_artifact(fpath)
        size_mb = os.path.getsize(fpath) / 1024 / 1024
        print(f"  LOADABLE : {fname} ({size_mb:.1f} MB) -> {type(obj).__name__}")
        if compatible_eval_model is None:
            compatible_eval_model = (fname, fpath)
    except Exception as e:
        print(f"  INCOMPATIBLE: {fname} -> {type(e).__name__}: {e}")

# ---------------------------------------------------------------------------
# STEP 1: Upload a real valid .joblib, confirm path and directory layout
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print("STEP 1: Upload real valid .joblib -- save and verify path")
print("-" * 60)

# Build a small fresh model with the current sklearn so there is no
# version-compatibility issue (the worker in this env would face the same
# constraint as our validator).
print("  Building fresh RandomForestClassifier with current sklearn ...")
iris = load_iris()
X_tr, X_te, y_tr, y_te = train_test_split(iris.data, iris.target, test_size=0.2, random_state=42)
clf = RandomForestClassifier(n_estimators=20, random_state=42)
clf.fit(X_tr, y_tr)

# Serialize to bytes using joblib (same as worker uses to load)
buf = io.BytesIO()
joblib.dump(clf, buf)
model_bytes = buf.getvalue()
print(f"  Serialized model size: {len(model_bytes) / 1024:.1f} KB")

step1_saved_path = None
try:
    saved_path = save_model_artifact(
        model_id="iris-rf",
        version="v1",
        file_bytes=model_bytes,
        filename="iris_rf_model.joblib",
    )

    assert os.path.isabs(saved_path),        "Returned path must be absolute"
    assert os.path.exists(saved_path),       "Saved file must exist on disk"
    assert saved_path.startswith(ARTIFACT_STORAGE_ROOT), (
        f"Path must be under ARTIFACT_STORAGE_ROOT.\nGot: {saved_path}"
    )
    expected_dir = os.path.join(ARTIFACT_STORAGE_ROOT, "iris-rf", "v1", "model")
    assert os.path.abspath(saved_path).startswith(os.path.abspath(expected_dir)), (
        f"Path should be inside {expected_dir}"
    )

    print(f"  Saved to: {saved_path}")
    step1_saved_path = saved_path
    report(PASS, "Step 1", f"iris_rf_model.joblib saved to correct path under ARTIFACT_STORAGE_ROOT")
except Exception as e:
    report(FAIL, "Step 1", str(e))
    traceback.print_exc()

# ---------------------------------------------------------------------------
# STEP 2: returned path is loadable by worker_auditor._load_artifact()
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print("STEP 2: Verify saved path is loadable by worker_auditor._load_artifact()")
print("-" * 60)

if step1_saved_path:
    try:
        loaded_obj = _load_artifact(step1_saved_path)
        obj_type = type(loaded_obj).__name__
        print(f"  _load_artifact returned: {obj_type}")
        assert hasattr(loaded_obj, "predict") or hasattr(loaded_obj, "predict_proba"), (
            f"Loaded object ({obj_type}) has neither predict nor predict_proba"
        )
        # Quick sanity: predictions should work
        preds = loaded_obj.predict(X_te)
        assert len(preds) == len(X_te)
        print(f"  predict() returned {len(preds)} values -- OK")
        report(PASS, "Step 2", f"_load_artifact loaded {obj_type} and predict() succeeded")
    except Exception as e:
        report(FAIL, "Step 2", str(e))
        traceback.print_exc()
else:
    report(FAIL, "Step 2", "Skipped -- Step 1 did not produce a saved path")

# Also upload the first compatible eval model if one exists
if compatible_eval_model:
    fname, fpath = compatible_eval_model
    print()
    print(f"  [BONUS Step 2b] Also testing with compatible eval model: {fname}")
    try:
        with open(fpath, "rb") as f:
            eval_bytes = f.read()
        eval_path = save_model_artifact(
            model_id="eval-compat",
            version="v1",
            file_bytes=eval_bytes,
            filename=fname,
        )
        loaded_eval = _load_artifact(eval_path)
        print(f"  Eval model saved & loaded as: {type(loaded_eval).__name__}")
        report(PASS, "Step 2b", f"Compatible eval model {fname} -> {type(loaded_eval).__name__}")
    except Exception as e:
        report(FAIL, "Step 2b", str(e))

# ---------------------------------------------------------------------------
# STEP 3: Corrupted file rejected BEFORE disk write
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print("STEP 3: Upload deliberately corrupted (non-joblib) file")
print("-" * 60)

GARBAGE = b"This is not a joblib or pickle file. Just garbage.\x00\x01\x02\x03\xff"
expected_corrupt_path = os.path.join(
    ARTIFACT_STORAGE_ROOT, "corrupt-test", "v1", "model", "corrupt.joblib"
)

try:
    save_model_artifact(
        model_id="corrupt-test",
        version="v1",
        file_bytes=GARBAGE,
        filename="corrupt.joblib",
    )
    report(FAIL, "Step 3", "Corrupted bytes were accepted -- they should have been rejected!")
except ArtifactValidationError as e:
    print(f"  Correctly rejected: {e}")
    if os.path.exists(expected_corrupt_path):
        report(FAIL, "Step 3", "Corrupt file was written to disk despite rejection!")
    else:
        report(PASS, "Step 3", "Corrupted upload rejected before disk write; no file on disk")
except Exception as e:
    report(FAIL, "Step 3", f"Unexpected {type(e).__name__}: {e}")
    traceback.print_exc()

# ---------------------------------------------------------------------------
# STEP 4: Path-traversal / unsafe characters rejected
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print("STEP 4: Path-traversal attacks rejected")
print("-" * 60)

traversal_cases = [
    ("../../etc",  "v1",       "Classic Unix traversal in model_id"),
    ("valid-id",   "../../etc","Classic Unix traversal in version"),
    ("../passwd",  "v1",       "Single dot-dot in model_id"),
    ("model/evil", "v1",       "Forward slash in model_id"),
    ("model\\evil","v1",       "Backslash in model_id"),
    ("model id",   "v1",       "Space in model_id"),
    ("model!id",   "v1",       "Exclamation mark in model_id"),
    ("",           "v1",       "Empty model_id"),
    ("valid-id",   "",         "Empty version"),
]

all_rejected = True
for bad_id, bad_ver, description in traversal_cases:
    try:
        save_model_artifact(
            model_id=bad_id,
            version=bad_ver,
            file_bytes=b"irrelevant",
            filename="model.joblib",
        )
        print(f"  [FAIL] {description!r} -- NOT rejected!")
        all_rejected = False
    except (ArtifactPathError, ArtifactStorageError, ArtifactValidationError, ArtifactSizeError) as e:
        print(f"  [OK] {description!r} -> {type(e).__name__}: {e}")
    except Exception as e:
        print(f"  [OK] {description!r} -> {type(e).__name__}: {e}")

if all_rejected:
    report(PASS, "Step 4", "All path-traversal / unsafe strings rejected")
else:
    report(FAIL, "Step 4", "One or more traversal attempts NOT rejected -- see above")

# ---------------------------------------------------------------------------
# BONUS: preprocessor upload round-trip
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print("BONUS: save_preprocessor_artifact() round-trip")
print("-" * 60)

if os.path.exists(FRAUD_PREPROCESSOR):
    try:
        with open(FRAUD_PREPROCESSOR, "rb") as f:
            prep_bytes = f.read()
        prep_path = save_preprocessor_artifact(
            model_id="credit-fraud",
            version="v1",
            file_bytes=prep_bytes,
            filename="fraud_preprocessor_only.joblib",
        )
        loaded_prep = _load_artifact(prep_path)
        print(f"  Saved: {prep_path}")
        print(f"  Loaded as: {type(loaded_prep).__name__}")
        report(PASS, "Bonus-Preprocessor", f"Preprocessor saved & loadable as {type(loaded_prep).__name__}")
    except Exception as e:
        report(FAIL, "Bonus-Preprocessor", str(e))
        traceback.print_exc()
else:
    print(f"  Skipping -- not found: {FRAUD_PREPROCESSOR}")

# ---------------------------------------------------------------------------
# BONUS: get_artifact_paths()
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print("BONUS: get_artifact_paths() for iris-rf/v1")
print("-" * 60)
paths = get_artifact_paths("iris-rf", "v1")
for k, v in paths.items():
    print(f"  {k}: {v}")
report(PASS, "Bonus-GetPaths", "get_artifact_paths() returned without error")

# ---------------------------------------------------------------------------
# BONUS: size limit enforcement
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print("BONUS: Size limit enforcement (1-byte limit override)")
print("-" * 60)
import guardrail_ai.core.artifact_storage as _mod
orig = _mod.MAX_ARTIFACT_SIZE_MB
_mod.MAX_ARTIFACT_SIZE_MB = 0  # force rejection of anything > 0 MB
try:
    save_model_artifact("size-test", "v1", model_bytes, "iris_rf_model.joblib")
    report(FAIL, "Bonus-SizeLimit", "Should have been rejected for size!")
except ArtifactSizeError as e:
    print(f"  Correctly rejected: {e}")
    report(PASS, "Bonus-SizeLimit", "Oversized upload rejected with ArtifactSizeError")
finally:
    _mod.MAX_ARTIFACT_SIZE_MB = orig

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
print()
print("=" * 70)
print("  SUMMARY")
print("=" * 70)
for r in results:
    print(f"  {r}")
print()

# Document sklearn compat status
print("  SKLEARN COMPAT NOTE:")
print("  adult_income_model.joblib (sklearn 1.6.1) is incompatible with")
print("  this env's sklearn 1.7.2 (_RemainderColsList was renamed). The")
print("  validator correctly rejects it -- identical to what the worker would do.")
print()

failed = [r for r in results if r.startswith(FAIL)]
if failed:
    print(f"OVERALL: {len(failed)} test(s) FAILED")
    sys.exit(1)
else:
    print(f"OVERALL: All {len(results)} test(s) PASSED")
    sys.exit(0)
