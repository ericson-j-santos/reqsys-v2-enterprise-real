#!/usr/bin/env python3
"""Pinned consumer for E2E Platform physical handoff evidence.

This adapter validates provenance and delegates evidence validation to the exact
published E2E Platform commit. It does not dispatch work or authorize merge/deploy.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts.validate_reqsys_native_dev_profile import NativeAdmissionBlocked

E2E_PLATFORM_SHA = "29278bbf9e84f851edbe66cd36ef0ca924521f7b"
VALIDATOR_RELATIVE_PATH = Path("scripts/validate_physical_handoff.py")
VALIDATOR_SHA256 = "f4503cee929235e98bd577058802be8ca221575493b66ebadf963d573ca86810"
ALLOWED_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise NativeAdmissionBlocked(code)


def consume_physical_handoff(
    *, platform_root: Path, evidence: Path, public_key_hex: str,
    expected_pr_number: int, expected_head_sha: str, expected_environment: str,
    expected_run_id: int, expected_job_id: int, expected_run_attempt: int,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    root = platform_root.resolve(strict=True)
    _require(platform_root.is_absolute() and root.is_dir() and not platform_root.is_symlink(),
             "e2e_platform_root_invalid")
    validator = root / VALIDATOR_RELATIVE_PATH
    _require(validator.is_file() and not validator.is_symlink(),
             "e2e_platform_validator_missing")
    _require(hashlib.sha256(validator.read_bytes()).hexdigest() == VALIDATOR_SHA256,
             "e2e_platform_validator_hash_mismatch")
    _require(evidence.is_absolute() and evidence.is_file() and not evidence.is_symlink(),
             "physical_evidence_file_invalid")
    _require(isinstance(public_key_hex, str) and len(public_key_hex) == 64 and
             all(ch in "0123456789abcdef" for ch in public_key_hex),
             "physical_evidence_public_key_invalid")
    _require(isinstance(expected_head_sha, str) and len(expected_head_sha) == 40 and
             all(ch in "0123456789abcdef" for ch in expected_head_sha),
             "physical_evidence_head_invalid")
    _require(all(type(value) is int and value > 0 for value in (
        expected_pr_number, expected_run_id, expected_job_id, expected_run_attempt)),
        "physical_evidence_execution_ids_invalid")

    git = run(["git", "-C", str(root), "rev-parse", "HEAD"],
              capture_output=True, text=True, timeout=15, check=False)
    _require(git.returncode == 0 and git.stdout.strip() == E2E_PLATFORM_SHA,
             "e2e_platform_sha_mismatch")
    command = [
        sys.executable, str(validator), str(evidence),
        "--public-key-hex", public_key_hex,
        "--expected-repository", ALLOWED_REPOSITORY,
        "--expected-pr-number", str(expected_pr_number),
        "--expected-head-sha", expected_head_sha,
        "--expected-environment", expected_environment,
        "--expected-run-id", str(expected_run_id),
        "--expected-job-id", str(expected_job_id),
        "--expected-run-attempt", str(expected_run_attempt),
    ]
    completed = run(command, capture_output=True, text=True, timeout=60, check=False)
    _require(completed.returncode == 0, "physical_handoff_evidence_blocked")
    try:
        result = json.loads(completed.stdout)
    except (TypeError, ValueError):
        raise NativeAdmissionBlocked("physical_handoff_result_invalid") from None
    _require(isinstance(result, dict) and
             result.get("result") == "PHYSICAL_HANDOFF_EVIDENCE_VALID" and
             result.get("repository") == ALLOWED_REPOSITORY and
             result.get("pr_number") == expected_pr_number and
             result.get("head_sha") == expected_head_sha and
             result.get("workflow_run_id") == expected_run_id and
             result.get("job_id") == expected_job_id and
             result.get("run_attempt") == expected_run_attempt and
             isinstance(result.get("physical_hosts"), list) and
             len(set(result["physical_hosts"])) == 2 and
             result.get("dispatch_allowed") is False and
             result.get("merge_authorized") is False and
             result.get("deployment_authorized") is False,
             "physical_handoff_result_mismatch")
    return {
        "status": "PHYSICAL_E2E_EXECUTION_BOUND_VALIDATED",
        "platform_sha": E2E_PLATFORM_SHA,
        "head_sha": expected_head_sha,
        "pr_number": expected_pr_number,
        "workflow_run_id": expected_run_id,
        "job_id": expected_job_id,
        "run_attempt": expected_run_attempt,
        "task_id": result.get("task_id"),
        "physical_hosts": sorted(result["physical_hosts"]),
        "native_physical_admitted": True,
        "dispatch_allowed": False,
        "merge_authorized": False,
        "deployment_authorized": False,
    }
