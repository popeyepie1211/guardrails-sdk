#!/usr/bin/env python
"""Provision API keys for already-registered models without exposing secrets."""

from __future__ import annotations

import argparse
import os
import re
import secrets
import tempfile
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from guardrail_ai.core.api_keys import generate_api_key, hash_api_key, verify_api_key


DEFAULT_MODEL_IDS = (
    "adult_income_model_v1",
    "house_price_model_v1",
    "credit_fraud_model_v1",
)


def _env_name(model_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", model_id).strip("_").upper()
    return f"MODEL_API_KEY_{normalized}"


def _write_env_file(path: Path, updates: dict[str, str]) -> None:
    """Atomically update selected dotenv values without printing them."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    remaining = dict(updates)
    updated_lines: list[str] = []

    for line in lines:
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match and match.group(1) in remaining:
            key = match.group(1)
            updated_lines.append(f"{key}={remaining.pop(key)}")
        else:
            updated_lines.append(line)

    if updated_lines and updated_lines[-1] != "":
        updated_lines.append("")
    updated_lines.extend(f"{key}={value}" for key, value in remaining.items())
    content = "\n".join(updated_lines) + "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temp_name, 0o600)
        except OSError:
            pass
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def provision(model_ids: list[str], env_file: Path) -> list[tuple[str, str]]:
    load_dotenv(dotenv_path=env_file, override=False)
    pepper = os.getenv("API_KEY_PEPPER")

    connection = psycopg.connect(
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "password"),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "postgres"),
    )
    provisioned: list[tuple[str, str]] = []
    env_updates: dict[str, str] = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM model_api_keys WHERE model_id = ANY(%s)",
                (model_ids,),
            )
            existing_key_count = cursor.fetchone()[0]
            if not pepper and existing_key_count:
                raise RuntimeError(
                    "API_KEY_PEPPER is unavailable for existing key hashes; "
                    "refusing to replace it or rotate keys silently."
                )
            if not pepper:
                pepper = secrets.token_urlsafe(48)
                os.environ["API_KEY_PEPPER"] = pepper
                env_updates["API_KEY_PEPPER"] = pepper

            for model_id in model_ids:
                cursor.execute("SELECT 1 FROM models WHERE model_id = %s", (model_id,))
                if cursor.fetchone() is None:
                    raise RuntimeError(f"Model {model_id!r} is not registered.")

                cursor.execute(
                    "SELECT 1 FROM model_api_keys WHERE model_id = %s",
                    (model_id,),
                )
                env_name = _env_name(model_id)
                if cursor.fetchone() is not None:
                    configured_key = os.getenv(env_name)
                    if not configured_key:
                        raise RuntimeError(
                            f"Model {model_id!r} already has a hash but {env_name} is unavailable; "
                            "refusing to rotate it silently."
                        )
                    cursor.execute(
                        "SELECT api_key_hash FROM model_api_keys WHERE model_id = %s",
                        (model_id,),
                    )
                    if not verify_api_key(configured_key, cursor.fetchone()[0]):
                        raise RuntimeError(
                            f"Configured key {env_name} does not match model {model_id!r}; "
                            "refusing to rotate it silently."
                        )
                    continue

                raw_api_key = generate_api_key()
                cursor.execute(
                    "INSERT INTO model_api_keys (model_id, api_key_hash) VALUES (%s, %s)",
                    (model_id, hash_api_key(raw_api_key)),
                )
                env_updates[env_name] = raw_api_key
                provisioned.append((model_id, env_name))

        if env_updates:
            _write_env_file(env_file, env_updates)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return provisioned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "model_ids",
        nargs="*",
        default=list(DEFAULT_MODEL_IDS),
        help="Registered model IDs (defaults to the three evaluation models).",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Ignored dotenv file that receives the raw keys (default: .env).",
    )
    args = parser.parse_args()

    provisioned = provision(args.model_ids, args.env_file.resolve())
    if not provisioned:
        print("All requested models already have configured API keys; nothing changed.")
        return 0

    print("Provisioned API keys without displaying their values:")
    for model_id, env_name in provisioned:
        print(f"  {model_id} -> {env_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
