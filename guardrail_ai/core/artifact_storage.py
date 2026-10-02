"""
guardrail_ai/core/artifact_storage.py

Persistent storage for user-uploaded model artifacts (.joblib / .pkl).

DESIGN APPROACH
---------------
Uploaded files are written to a local directory tree:

    <ARTIFACT_STORAGE_ROOT>/<model_id>/<version>/<artifact_type>/

where ARTIFACT_STORAGE_ROOT defaults to:

    <repo_root>/model_artifacts/

The returned path is an absolute filesystem path that worker_auditor.py's
existing _load_artifact() / _load_background_frame() functions can consume
directly -- no changes to those functions are required.

KNOWN SCOPE LIMITATION -- SINGLE-MACHINE ONLY
----------------------------------------------
This design assumes the registration service (which calls save_*()) and the
worker process (which calls _load_artifact()) share the same physical
filesystem. That is true in the current single-machine deployment where both
run on the same host.

It does NOT support a distributed / multi-machine worker deployment. In that
topology a file written on the web-server machine would not be visible to a
worker running on a different host. Supporting that scenario requires:
  * An object-storage backend (e.g. AWS S3, GCS, Azure Blob)
  * The worker downloading / caching artifacts on first use (lazy fetch)
  * Or a shared network filesystem (NFS, EFS, etc.)

This is a deliberate scope boundary -- it is NOT silently glossed over.
"""

import io
import os
import re
import pickle
import logging
import tempfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (all values are env-var-overridable)
# ---------------------------------------------------------------------------

# Root directory for all stored artifacts.
# Defaults to  <repo_root>/model_artifacts/  (two levels up from this file).
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
ARTIFACT_STORAGE_ROOT: str = os.environ.get(
    "ARTIFACT_STORAGE_ROOT",
    os.path.join(_REPO_ROOT, "model_artifacts"),
)

# Maximum allowed upload size in megabytes (env: MAX_ARTIFACT_SIZE_MB).
MAX_ARTIFACT_SIZE_MB: int = int(os.environ.get("MAX_ARTIFACT_SIZE_MB", "500"))

# Allowed file extensions for model/preprocessor artifacts.
_ALLOWED_MODEL_EXTENSIONS = {".joblib", ".pkl"}
# Allowed file extensions for SHAP background data.
_ALLOWED_BACKGROUND_EXTENSIONS = {".csv"}

# Regex that defines the characters allowed in model_id / version strings.
# Only alphanumerics, hyphens and underscores are permitted.
# Everything else (including "/" and ".") is rejected outright.
_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class ArtifactStorageError(Exception):
    """Raised when an upload is rejected before being written to disk."""


class ArtifactValidationError(ArtifactStorageError):
    """Raised when bytes cannot be deserialized as a valid joblib/pickle object."""


class ArtifactSizeError(ArtifactStorageError):
    """Raised when the uploaded file exceeds MAX_ARTIFACT_SIZE_MB."""


class ArtifactPathError(ArtifactStorageError):
    """Raised when model_id or version contain unsafe characters."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sanitize_component(value: str, label: str) -> str:
    """
    Validate and return *value* if it is safe to embed in a filesystem path.

    Rules
    -----
    * Must be non-empty.
    * Must match ``^[A-Za-z0-9_\\-]+$`` -- alphanumerics, hyphens, underscores.
    * Must NOT contain path-traversal sequences (``..``, ``/``, ``\\``).

    Raises ArtifactPathError for any violation.
    """
    if not value or not value.strip():
        raise ArtifactPathError(f"{label} must be a non-empty string.")

    value = value.strip()

    # Explicit check for path-traversal sequences before regex validation.
    if ".." in value or "/" in value or "\\" in value:
        raise ArtifactPathError(
            f"{label} contains path-traversal characters and was rejected: {value!r}"
        )

    if not _SAFE_COMPONENT_RE.match(value):
        raise ArtifactPathError(
            f"{label} contains unsafe characters (only A-Z, a-z, 0-9, '_', '-' are allowed): {value!r}"
        )

    return value


def _check_size(file_bytes: bytes, filename: str) -> None:
    """Reject uploads that exceed MAX_ARTIFACT_SIZE_MB."""
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_ARTIFACT_SIZE_MB:
        raise ArtifactSizeError(
            f"Upload rejected: {filename!r} is {size_mb:.1f} MB, which exceeds "
            f"the {MAX_ARTIFACT_SIZE_MB} MB limit (set MAX_ARTIFACT_SIZE_MB env var to change)."
        )


def _validate_joblib_bytes(file_bytes: bytes, filename: str) -> None:
    """
    Attempt to deserialize *file_bytes* as a joblib/pickle object.

    The deserialized object is intentionally discarded -- we only need to
    confirm the bytes are well-formed. Uses a TemporaryFile to avoid writing
    corrupted data to permanent storage.

    Raises ArtifactValidationError if deserialization fails.
    """
    import joblib  # imported here so the rest of the module works without joblib

    ext = os.path.splitext(filename)[1] or ".joblib"
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_name = tmp.name
            tmp.write(file_bytes)
            tmp.flush()

        try:
            joblib.load(tmp_name)
            logger.debug("joblib.load succeeded for %s", filename)
            return
        except Exception as joblib_err:
            # Fall back to pickle before giving up.
            try:
                with open(tmp_name, "rb") as f:
                    pickle.load(f)
                logger.debug("pickle.load succeeded for %s (joblib failed: %s)", filename, joblib_err)
                return
            except Exception as pkl_err:
                raise ArtifactValidationError(
                    f"Upload rejected: {filename!r} is not a valid joblib/pickle file. "
                    f"joblib error: {joblib_err}; pickle error: {pkl_err}"
                ) from pkl_err
    except ArtifactValidationError:
        raise
    except Exception as e:
        raise ArtifactValidationError(
            f"Upload rejected: could not validate {filename!r} -- unexpected error: {e}"
        ) from e
    finally:
        try:
            os.remove(tmp_name)
        except OSError:
            pass


def _build_artifact_dir(model_id: str, version: str, artifact_type: str) -> str:
    """
    Construct and create (if needed) the storage directory for an artifact.

    Directory layout::

        <ARTIFACT_STORAGE_ROOT>/<model_id>/<version>/<artifact_type>/

    *artifact_type* is an internal constant like "model", "preprocessor",
    or "background" -- it is never derived from user input.
    """
    artifact_dir = os.path.join(ARTIFACT_STORAGE_ROOT, model_id, version, artifact_type)
    os.makedirs(artifact_dir, exist_ok=True)
    return artifact_dir


def _write_artifact(artifact_dir: str, filename: str, file_bytes: bytes) -> str:
    """
    Write *file_bytes* atomically to *artifact_dir*/*filename*.

    Uses a sibling temp file + os.replace() so a partial write never leaves a
    corrupt file at the final path.

    Returns the absolute path of the saved file.
    """
    final_path = os.path.join(artifact_dir, filename)
    tmp_path = final_path + ".tmp"
    try:
        with open(tmp_path, "wb") as fh:
            fh.write(file_bytes)
        os.replace(tmp_path, final_path)  # atomic on POSIX; best-effort on Windows
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

    logger.info("Artifact saved: %s (%d bytes)", final_path, len(file_bytes))
    return os.path.abspath(final_path)


def _safe_extension(filename: str, allowed: set, label: str) -> str:
    """Return lowercased extension if it is in *allowed*, else raise."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in allowed:
        raise ArtifactStorageError(
            f"{label} file {filename!r} has an unsupported extension {ext!r}. "
            f"Allowed: {sorted(allowed)}"
        )
    return ext


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_model_artifact(
    model_id: str,
    version: str,
    file_bytes: bytes,
    filename: str,
) -> str:
    """
    Validate and persistently store a model artifact uploaded by the user.

    Steps performed (in order, so nothing is written on rejection):
      1. Sanitize *model_id* and *version* -- reject path-traversal / unsafe chars.
      2. Validate file extension (.joblib or .pkl only).
      3. Enforce file size limit (MAX_ARTIFACT_SIZE_MB).
      4. Attempt a real joblib/pickle deserialization -- reject corrupt bytes.
      5. Write bytes atomically to permanent storage.

    Parameters
    ----------
    model_id : str
        Unique model identifier.  Must match ``^[A-Za-z0-9_-]+$``.
    version : str
        Model version string.  Same character constraints as model_id.
    file_bytes : bytes
        Raw bytes of the uploaded file.
    filename : str
        Original filename supplied by the uploader (used for extension check
        and as the on-disk filename).

    Returns
    -------
    str
        Absolute filesystem path of the saved artifact, ready to be stored in
        ``model_baselines.metadata.model_artifact_path``.

    Raises
    ------
    ArtifactPathError
        model_id or version contain unsafe characters.
    ArtifactStorageError
        Unsupported file extension.
    ArtifactSizeError
        File exceeds MAX_ARTIFACT_SIZE_MB.
    ArtifactValidationError
        Bytes are not a valid joblib/pickle object.
    """
    # 1. Sanitize path components -- SECURITY: must happen before any fs ops.
    safe_id = _sanitize_component(model_id, "model_id")
    safe_ver = _sanitize_component(version, "version")

    # 2. Extension check.
    _safe_extension(filename, _ALLOWED_MODEL_EXTENSIONS, "Model")

    # 3. Size check -- before any deserialization.
    _check_size(file_bytes, filename)

    # 4. Validate that bytes are actually a real, loadable model.
    logger.info("Validating model artifact %r (%d bytes) ...", filename, len(file_bytes))
    _validate_joblib_bytes(file_bytes, filename)

    # 5. Write to permanent storage.
    artifact_dir = _build_artifact_dir(safe_id, safe_ver, "model")
    return _write_artifact(artifact_dir, filename, file_bytes)


def save_preprocessor_artifact(
    model_id: str,
    version: str,
    file_bytes: bytes,
    filename: str,
) -> str:
    """
    Validate and persistently store a preprocessor artifact uploaded by the user.

    Identical validation pipeline to save_model_artifact() --
    extension, size, and real joblib/pickle deserialization checks are all
    applied before any bytes reach disk.

    Returns
    -------
    str
        Absolute path ready for ``model_baselines.metadata.preprocessor_artifact_path``.
    """
    safe_id = _sanitize_component(model_id, "model_id")
    safe_ver = _sanitize_component(version, "version")
    _safe_extension(filename, _ALLOWED_MODEL_EXTENSIONS, "Preprocessor")
    _check_size(file_bytes, filename)

    logger.info("Validating preprocessor artifact %r (%d bytes) ...", filename, len(file_bytes))
    _validate_joblib_bytes(file_bytes, filename)

    artifact_dir = _build_artifact_dir(safe_id, safe_ver, "preprocessor")
    return _write_artifact(artifact_dir, filename, file_bytes)


def save_background_artifact(
    model_id: str,
    version: str,
    file_bytes: bytes,
    filename: str,
) -> str:
    """
    Persistently store a SHAP background CSV uploaded by the user.

    Validation applied:
      * Sanitize model_id / version.
      * Extension must be .csv.
      * File must not exceed MAX_ARTIFACT_SIZE_MB.
      * File must be parseable as a CSV (non-empty, at least one column).

    No joblib/pickle validation is performed because background data is a CSV,
    not a serialized model object.

    Returns
    -------
    str
        Absolute path ready for ``model_baselines.metadata.shap_background_path``.
    """
    import csv

    safe_id = _sanitize_component(model_id, "model_id")
    safe_ver = _sanitize_component(version, "version")
    _safe_extension(filename, _ALLOWED_BACKGROUND_EXTENSIONS, "Background")
    _check_size(file_bytes, filename)

    # Validate that the bytes are parseable CSV with at least a header row.
    logger.info("Validating background CSV %r (%d bytes) ...", filename, len(file_bytes))
    try:
        text = file_bytes.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header:
            raise ArtifactValidationError(
                f"Upload rejected: {filename!r} appears to be an empty CSV."
            )
        logger.debug("Background CSV header: %s", header)
    except ArtifactValidationError:
        raise
    except Exception as e:
        raise ArtifactValidationError(
            f"Upload rejected: {filename!r} is not a valid CSV file -- {e}"
        ) from e

    artifact_dir = _build_artifact_dir(safe_id, safe_ver, "background")
    return _write_artifact(artifact_dir, filename, file_bytes)


def get_artifact_paths(model_id: str, version: str) -> dict:
    """
    Return a dict of all artifact paths that currently exist on disk for the
    given model_id / version.  Useful for inspection / debugging.

    Returns keys: 'model', 'preprocessor', 'background'.
    Values are lists of absolute paths (may be empty if no files were saved).
    """
    safe_id = _sanitize_component(model_id, "model_id")
    safe_ver = _sanitize_component(version, "version")

    result: dict = {"model": [], "preprocessor": [], "background": []}
    for artifact_type in result:
        artifact_dir = os.path.join(ARTIFACT_STORAGE_ROOT, safe_id, safe_ver, artifact_type)
        if os.path.isdir(artifact_dir):
            result[artifact_type] = [
                os.path.abspath(os.path.join(artifact_dir, f))
                for f in os.listdir(artifact_dir)
                if not f.endswith(".tmp")
            ]
    return result
