#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
import uuid

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
E2E_SCRIPT = RUNTIME_ROOT / "scripts" / "e2e_central.py"
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

REQUIRED_MARKERS = (
    "PASS  registro_201",
    "PASS  evidencia_evidenced",
    "PASS  conclusao_aceita_com_evidencia",
    "PASS  conclusao_recusada_sem_evidencia_completa",
    "PASS  conclusao_recusada_apos_mudanca_de_sha",
    "PASS  human_gate_fora_da_fila_executavel",
    "PASS  registro_idempotente_sem_duplicata",
    "PASS  leitura_independente_ledger",
)


def require_markers(output: str) -> None:
    missing = [marker for marker in REQUIRED_MARKERS if marker not in output]
    if missing:
        raise RuntimeError("e2e_required_markers_missing:" + ",".join(missing))


def validate_identity(repository: str, sha: str) -> None:
    if not REPOSITORY_RE.fullmatch(repository):
        raise RuntimeError("repository_invalid")
    if not SHA_RE.fullmatch(sha):
        raise RuntimeError("sha_must_be_full_40_chars")


def build_evidence(
    *,
    repository: str,
    sha: str,
    environment: str,
    correlation_id: str,
    started_at: datetime,
    completed_at: datetime,
) -> dict[str, object]:
    validate_identity(repository, sha)
    return {
        "schema_version": "1.0.0",
        "project": "ReqSys Central Global",
        "repository": repository,
        "sha": sha.lower(),
        "environment": environment,
        "correlation_id": correlation_id,
        "objective": "Validar Central Global real e comprovar consumo do e2e-platform.",
        "status": "passed",
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
        "positive_control": {
            "passed": True,
            "evidence": "registro_201; evidencia_evidenced; conclusao_aceita_com_evidencia",
        },
        "negative_control": {
            "applicable": True,
            "passed": True,
            "evidence": (
                "conclusao_recusada_sem_evidencia_completa; "
                "conclusao_recusada_apos_mudanca_de_sha; "
                "human_gate_fora_da_fila_executavel"
            ),
        },
        "independent_read": {
            "passed": True,
            "source": "GET /api/central/evidence/{request_id}",
            "evidence": "leitura_independente_ledger",
        },
        "idempotency": {
            "applicable": True,
            "passed": True,
            "evidence": "registro_idempotente_mesmo_id; registro_idempotente_sem_duplicata",
        },
        "test_of_test": {
            "applicable": False,
            "passed": None,
            "evidence": "Coberto pelo self-test fail-closed do e2e-platform.",
        },
    }


def wait_for_health(base_url: str, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not_started"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/health", timeout=2) as response:
                if response.status == 200:
                    return
                last_error = f"http_{response.status}"
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(0.5)
    raise RuntimeError(f"runtime_health_timeout:{last_error}")


def run_pilot(output_path: Path) -> dict[str, object]:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    environment = os.environ.get("E2E_ENVIRONMENT", "ci")
    correlation_id = os.environ.get("E2E_CORRELATION_ID") or f"reqsys-central-{uuid.uuid4().hex[:16]}"
    validate_identity(repository, sha)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = output_path.with_name("central-e2e.log")
    runtime_log_path = output_path.with_name("runtime.log")
    base_url = "http://127.0.0.1:8099"
    started_at = datetime.now(UTC)

    env = os.environ.copy()
    env.update(
        {
            "QUEUE_BACKEND": "memory",
            "STORAGE_BACKEND": "memory",
            "RUNTIME_ENVIRONMENT": "test",
            "CENTRAL_E2E_BASE_URL": base_url,
            "CENTRAL_E2E_CORRELATION_ID": correlation_id,
        }
    )

    with runtime_log_path.open("w", encoding="utf-8") as runtime_log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8099",
            ],
            cwd=RUNTIME_ROOT,
            env=env,
            stdout=runtime_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            wait_for_health(base_url)
            completed = subprocess.run(
                [sys.executable, str(E2E_SCRIPT)],
                cwd=RUNTIME_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            combined = completed.stdout + completed.stderr
            log_path.write_text(combined, encoding="utf-8")
            if completed.returncode != 0:
                raise RuntimeError(f"central_e2e_failed:{completed.returncode}")
            require_markers(combined)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    evidence = build_evidence(
        repository=repository,
        sha=sha,
        environment=environment,
        correlation_id=correlation_id,
        started_at=started_at,
        completed_at=datetime.now(UTC),
    )
    output_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/e2e-platform/central/evidence.json"),
    )
    args = parser.parse_args()
    try:
        evidence = run_pilot(args.output)
    except Exception as exc:
        print(json.dumps({"result": "REQSYS_E2E_PLATFORM_PILOT_FAILED", "error": str(exc)}))
        return 1
    print(
        json.dumps(
            {
                "result": "REQSYS_E2E_PLATFORM_PILOT_PASSED",
                "sha": evidence["sha"],
                "correlation_id": evidence["correlation_id"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
