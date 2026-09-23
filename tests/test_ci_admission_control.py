from __future__ import annotations

import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCRIPT = ROOT / "scripts" / "ci_admission_manifest.py"
GUARD_SCRIPT = ROOT / "scripts" / "ci_admission_guard.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


manifest = load_module("ci_admission_manifest", MANIFEST_SCRIPT)
guard = load_module("ci_admission_guard", GUARD_SCRIPT)


def readiness(*, status: str = "passed", blockers: list[str] | None = None, profiles: list[str] | None = None):
    return {
        "schema_version": "1.1.0",
        "status": status,
        "correlation_id": "corr-1",
        "base_ref": "main",
        "base_sha": "b" * 40,
        "head_sha": "a" * 40,
        "behind_by": 0,
        "changed_files": ["scripts/ci_admission_guard.py"],
        "profiles": profiles or ["operational"],
        "checks": [],
        "preventive_invariants": [
            {"name": "sdd:contract", "status": "passed", "detail": "ok"},
            {"name": "security:changed-diff", "status": "passed", "detail": "ok"},
            {"name": "workflow:surface-budget", "status": "passed", "detail": "ok"},
            {"name": "workflow:regression-contracts", "status": "passed", "detail": "ok"},
        ],
        "blockers": blockers or [],
        "warnings": [],
    }


def test_manifest_admits_exact_sha_and_marks_ollama_optional() -> None:
    result = manifest.build_manifest(readiness(), "a" * 40)
    assert result["status"] == "admitted"
    assert result["head_sha"] == "a" * 40
    assert "Pre-PR Readiness Gate" in result["required_workflows"]
    assert "CI — ReqSys v2 Enterprise" in result["required_workflows"]
    assert {item["name"] for item in result["preventive_invariants"]} == manifest.REQUIRED_PREVENTIVE_INVARIANTS
    ollama = next(item for item in result["dependencies"] if item["name"] == "ollama_ci_triage")
    assert ollama["required"] is False
    assert ollama["failure_policy"] == "deterministic_fallback"


def test_manifest_classifies_stale_source_and_blocks() -> None:
    result = manifest.build_manifest(
        readiness(status="blocked", blockers=["branch está 2 commit(s) atrás de main; atualizar antes da PR"]),
        "a" * 40,
    )
    assert result["status"] == "blocked"
    assert result["blocker_reason"][0]["code"] == "SOURCE_STALE"


def test_manifest_rejects_evidence_from_another_sha() -> None:
    try:
        manifest.build_manifest(readiness(), "c" * 40)
    except manifest.AdmissionError as exc:
        assert "head_sha_mismatch" in str(exc)
    else:
        raise AssertionError("evidência de outro SHA deveria ser rejeitada")


def test_guard_accepts_only_successful_pre_pr_on_exact_sha() -> None:
    head = "a" * 40
    runs = [
        {"id": 1, "name": "Pre-PR Readiness Gate", "head_sha": "b" * 40, "status": "completed", "conclusion": "success", "updated_at": "2026-09-22T10:00:00Z"},
        {"id": 2, "name": "Pre-PR Readiness Gate", "head_sha": head, "status": "completed", "conclusion": "failure", "updated_at": "2026-09-22T10:01:00Z"},
        {"id": 3, "name": "Pre-PR Readiness Gate", "head_sha": head, "status": "completed", "conclusion": "success", "updated_at": "2026-09-22T10:02:00Z"},
    ]
    selected = guard.successful_pre_pr_runs(runs, head)
    assert [item["id"] for item in selected] == [3]


def test_guard_rejects_old_or_expired_admission_artifact() -> None:
    head = "a" * 40
    assert guard.matching_artifact([{"name": f"ci-admission-{'b' * 40}", "expired": False}], head) is None
    assert guard.matching_artifact([{"name": f"ci-admission-{head}", "expired": True}], head) is None
    artifact = {"id": 10, "name": f"ci-admission-{head}", "expired": False}
    assert guard.matching_artifact([artifact], head) == artifact


def test_guard_rejects_stale_or_diverged_source() -> None:
    try:
        guard.evaluate_compare(
            {"status": "diverged", "behind_by": 1, "ahead_by": 2},
            "b" * 40,
            "a" * 40,
        )
    except guard.AdmissionGuardError as exc:
        assert "source_stale_or_diverged" in str(exc)
        assert "behind_by=1" in str(exc)
    else:
        raise AssertionError("branch atrás/divergida deveria ser bloqueada")


def test_guard_accepts_head_based_on_current_base() -> None:
    result = guard.evaluate_compare(
        {"status": "ahead", "behind_by": 0, "ahead_by": 1},
        "b" * 40,
        "a" * 40,
    )
    assert result == {"status": "ahead", "behind_by": 0, "ahead_by": 1}


def test_pre_pr_generates_and_enforces_admission_manifest() -> None:
    raw = (ROOT / ".github/workflows/pre-pr-readiness.yml").read_text(encoding="utf-8")
    assert "scripts/ci_admission_manifest.py" in raw
    assert "ci-admission-${{ env.EVALUATED_SHA }}" in raw
    assert "CI_ADMISSION_ACCEPTED" in raw


def test_expensive_pr_workflows_are_guarded_before_router_or_guardrails() -> None:
    expectations = {
        ".github/workflows/ci.yml": "needs: ci-admission",
        ".github/workflows/ci-enterprise-fast.yml": "needs: ci-admission",
        ".github/workflows/ci-e2e-governado.yml": "needs: ci-admission",
    }
    for rel, expected in expectations.items():
        raw = (ROOT / rel).read_text(encoding="utf-8")
        assert "CI Admission Controller" in raw
        assert "scripts/ci_admission_guard.py" in raw
        assert "--base-ref" in raw
        assert expected in raw


def test_pr_evidence_gate_requires_manifest_from_current_sha() -> None:
    raw = (ROOT / ".github/workflows/pr-evidence-gate.yml").read_text(encoding="utf-8")
    assert "Pre-PR Readiness Gate" in raw
    assert "Admission manifest missing for current head SHA" in raw
    assert "artifact.name === admissionArtifactName" in raw
    assert "head_sha: headSha" in raw


def test_manifest_blocks_when_required_preventive_invariant_is_missing() -> None:
    payload = readiness()
    payload["preventive_invariants"] = [
        {"name": "sdd:contract", "status": "passed", "detail": "ok"},
        {"name": "security:changed-diff", "status": "passed", "detail": "ok"},
    ]
    result = manifest.build_manifest(payload, "a" * 40)
    assert result["status"] == "blocked"
    assert any(
        item["code"] == "PREVENTIVE_INVARIANT_FAILED"
        and "workflow:regression-contracts" in item["message"]
        for item in result["blocker_reason"]
    )


def test_guard_validates_manifest_content_not_only_artifact_name() -> None:
    head = "a" * 40
    base = "b" * 40
    payload = manifest.build_manifest(readiness(), head)
    validated = guard.validate_manifest_payload(payload, head, base)
    assert validated["status"] == "admitted"
    assert validated["head_sha"] == head

    payload["preventive_invariants"][0]["status"] = "failed"
    try:
        guard.validate_manifest_payload(payload, head, base)
    except guard.AdmissionGuardError as exc:
        assert "invariants_failed" in str(exc)
    else:
        raise AssertionError("manifesto com invariante falho deveria ser rejeitado")


def test_guard_rejects_manifest_with_wrong_base_sha() -> None:
    head = "a" * 40
    payload = manifest.build_manifest(readiness(), head)
    try:
        guard.validate_manifest_payload(payload, head, "c" * 40)
    except guard.AdmissionGuardError as exc:
        assert "base_sha_mismatch" in str(exc)
    else:
        raise AssertionError("manifesto de outra base deveria ser rejeitado")


def test_guard_extracts_exact_manifest_file_from_artifact_zip() -> None:
    head = "a" * 40
    payload = manifest.build_manifest(readiness(), head)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"{head}.json", json.dumps(payload))
    assert guard.manifest_from_zip(buffer.getvalue(), head)["head_sha"] == head


def test_manifest_marks_exact_base_empty_diff_as_not_applicable() -> None:
    payload = readiness(status="not_applicable", profiles=[])
    payload["base_sha"] = "a" * 40
    payload["head_sha"] = "a" * 40
    payload["changed_files"] = []
    payload["preventive_invariants"] = []
    result = manifest.build_manifest(payload, "a" * 40)
    assert result["status"] == "not_applicable"
    assert result["required_workflows"] == []
    assert result["blocker_reason"] == []


def test_manifest_rejects_not_applicable_when_a_real_diff_exists() -> None:
    payload = readiness(status="not_applicable", profiles=[])
    payload["base_sha"] = "a" * 40
    payload["head_sha"] = "a" * 40
    payload["changed_files"] = ["scripts/change.py"]
    payload["preventive_invariants"] = []
    try:
        manifest.build_manifest(payload, "a" * 40)
    except manifest.AdmissionError as exc:
        assert "not_applicable_state_invalid" in str(exc)
    else:
        raise AssertionError("not_applicable com diff real deveria ser rejeitado")
