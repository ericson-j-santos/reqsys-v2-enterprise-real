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
PR_NUMBER = 3050


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
        {"id": 1, "name": "Pre-PR Readiness Gate", "head_sha": "b" * 40, "event": "pull_request", "pull_requests": [{"number": PR_NUMBER}], "status": "completed", "conclusion": "success", "updated_at": "2026-09-22T10:00:00Z"},
        {"id": 2, "name": "Pre-PR Readiness Gate", "head_sha": head, "event": "pull_request", "pull_requests": [{"number": PR_NUMBER}], "status": "completed", "conclusion": "failure", "updated_at": "2026-09-22T10:01:00Z"},
        {"id": 3, "name": "Pre-PR Readiness Gate", "head_sha": head, "event": "pull_request", "pull_requests": [{"number": PR_NUMBER}], "status": "completed", "conclusion": "success", "updated_at": "2026-09-22T10:02:00Z"},
        {"id": 4, "name": "Pre-PR Readiness Gate", "head_sha": head, "event": "push", "pull_requests": [{"number": PR_NUMBER}], "status": "completed", "conclusion": "success", "updated_at": "2026-09-22T10:03:00Z"},
        {"id": 5, "name": "Pre-PR Readiness Gate", "head_sha": head, "event": "pull_request", "pull_requests": [{"number": PR_NUMBER + 1}], "status": "completed", "conclusion": "success", "updated_at": "2026-09-22T10:04:00Z"},
    ]
    selected = guard.successful_pre_pr_runs(runs, head, PR_NUMBER)
    assert [item["id"] for item in selected] == [3]


def test_guard_queries_canonical_pre_pr_workflow(monkeypatch) -> None:
    head = "a" * 40
    base = "b" * 40
    paths: list[str] = []

    def fake_github_json(repository: str, path: str, token: str):
        paths.append(path)
        if path.startswith("actions/workflows/pre-pr-readiness.yml/runs?"):
            return {
                "workflow_runs": [
                    {
                        "id": 7,
                        "name": guard.WORKFLOW_NAME,
                        "head_sha": head,
                        "event": "pull_request",
                        "pull_requests": [{"number": PR_NUMBER}],
                        "status": "completed",
                        "conclusion": "success",
                        "updated_at": "2026-10-03T10:00:00Z",
                    }
                ]
            }
        if path == "actions/runs/7/artifacts?per_page=100":
            return {
                "artifacts": [
                    {"id": 11, "name": f"ci-admission-{head}", "expired": False}
                ]
            }
        raise AssertionError(f"consulta inesperada: {path}")

    monkeypatch.setattr(guard, "github_json", fake_github_json)
    monkeypatch.setattr(
        guard,
        "load_and_validate_manifest",
        lambda repository, artifact, head_sha, base_sha, token: {"status": "admitted"},
    )

    result = guard.verify_evidence("owner/repo", head, base, "token", PR_NUMBER)

    assert result["pre_pr_run_id"] == 7
    assert paths[0].startswith("actions/workflows/pre-pr-readiness.yml/runs?")
    assert "actions/runs?" not in paths[0]


def test_guard_falls_back_when_filtered_lookup_is_empty(monkeypatch) -> None:
    head = "a" * 40
    base = "b" * 40
    paths: list[str] = []

    def fake_github_json(repository: str, path: str, token: str):
        paths.append(path)
        if "head_sha=" in path:
            return {"workflow_runs": []}
        if path.endswith("per_page=100&page=1"):
            return {
                "workflow_runs": [
                    {
                        "id": 6,
                        "name": guard.WORKFLOW_NAME,
                        "head_sha": head,
                        "event": "push",
                        "pull_requests": [{"number": PR_NUMBER}],
                        "status": "completed",
                        "conclusion": "success",
                    },
                    {
                        "id": 8,
                        "name": guard.WORKFLOW_NAME,
                        "head_sha": head,
                        "event": "pull_request",
                        "pull_requests": [{"number": PR_NUMBER + 1}],
                        "status": "completed",
                        "conclusion": "success",
                    },
                    {
                        "id": 7,
                        "name": guard.WORKFLOW_NAME,
                        "head_sha": head,
                        "event": "pull_request",
                        "pull_requests": [{"number": PR_NUMBER}],
                        "status": "completed",
                        "conclusion": "success",
                    },
                ]
            }
        if path == "actions/runs/7/artifacts?per_page=100":
            return {
                "artifacts": [
                    {"id": 11, "name": f"ci-admission-{head}", "expired": False}
                ]
            }
        raise AssertionError(f"consulta inesperada: {path}")

    monkeypatch.setattr(guard, "github_json", fake_github_json)
    monkeypatch.setattr(
        guard,
        "load_and_validate_manifest",
        lambda repository, artifact, head_sha, base_sha, token: {"status": "admitted"},
    )

    result = guard.verify_evidence("owner/repo", head, base, "token", PR_NUMBER)

    assert result["pre_pr_run_id"] == 7
    assert any(path.endswith("per_page=100&page=1") for path in paths)
    assert "actions/runs/6/artifacts?per_page=100" not in paths


def test_guard_fallback_never_accepts_push_or_wrong_pr_artifact(monkeypatch) -> None:
    head = "a" * 40
    paths: list[str] = []

    def fake_github_json(repository: str, path: str, token: str):
        paths.append(path)
        if "head_sha=" in path:
            return {"workflow_runs": []}
        if path.endswith("per_page=100&page=1"):
            return {
                "workflow_runs": [
                    {
                        "id": 99,
                        "name": guard.WORKFLOW_NAME,
                        "head_sha": head,
                        "event": "push",
                        "pull_requests": [{"number": PR_NUMBER}],
                        "status": "completed",
                        "conclusion": "success",
                    },
                    {
                        "id": 100,
                        "name": guard.WORKFLOW_NAME,
                        "head_sha": head,
                        "event": "pull_request",
                        "pull_requests": [{"number": PR_NUMBER + 1}],
                        "status": "completed",
                        "conclusion": "success",
                    }
                ]
            }
        raise AssertionError(f"consulta inesperada: {path}")

    monkeypatch.setattr(guard, "github_json", fake_github_json)

    try:
        guard.verify_evidence("owner/repo", head, "c" * 40, "token", PR_NUMBER)
    except guard.AdmissionGuardError as exc:
        assert str(exc) == "pre_pr_success_missing_for_head_sha"
    else:
        raise AssertionError("run push ou de outra PR não deveria ser aceito")
    assert not any(path.startswith("actions/runs/") for path in paths)


def test_guard_fallback_is_bounded_to_five_pages(monkeypatch) -> None:
    head = "a" * 40
    paths: list[str] = []

    def fake_github_json(repository: str, path: str, token: str):
        paths.append(path)
        if "head_sha=" in path:
            return {"workflow_runs": []}
        return {
            "workflow_runs": [
                {
                    "id": page_id,
                    "name": guard.WORKFLOW_NAME,
                    "head_sha": "b" * 40,
                    "event": "pull_request",
                    "pull_requests": [{"number": PR_NUMBER}],
                    "status": "completed",
                    "conclusion": "success",
                }
                for page_id in range(1, 101)
            ]
        }

    monkeypatch.setattr(guard, "github_json", fake_github_json)

    assert guard.list_pre_pr_runs("owner/repo", head, PR_NUMBER, "token") == []
    fallback_paths = [path for path in paths if "head_sha=" not in path]
    assert len(fallback_paths) == guard.WORKFLOW_RUN_FALLBACK_MAX_PAGES
    assert fallback_paths[-1].endswith("per_page=100&page=5")
    assert not any("page=6" in path for path in fallback_paths)


def test_guard_fallback_preserves_pending_and_failed_classification(monkeypatch) -> None:
    head = "a" * 40
    paths: list[str] = []

    def fake_for(state: str, result: str | None):
        def fake_github_json(repository: str, path: str, token: str):
            paths.append(path)
            if "head_sha=" in path:
                return {
                    "workflow_runs": [
                        {
                            "id": 7,
                            "name": guard.WORKFLOW_NAME,
                            "head_sha": head,
                            "event": "pull_request",
                            "pull_requests": [{"number": PR_NUMBER}],
                            "status": state,
                            "conclusion": result,
                        }
                    ]
                }
            raise AssertionError("fallback não deveria rodar quando a consulta exata tem match")

        return fake_github_json

    for status, conclusion, expected in (
        ("in_progress", None, "pre_pr_pending_for_head_sha"),
        ("completed", "failure", "pre_pr_failed_for_head_sha"),
    ):
        monkeypatch.setattr(guard, "github_json", fake_for(status, conclusion))
        try:
            guard.verify_evidence(
                "owner/repo",
                head,
                "b" * 40,
                "token",
                PR_NUMBER,
            )
        except guard.AdmissionGuardError as exc:
            assert str(exc) == expected
        else:
            raise AssertionError(f"estado {status}/{conclusion} deveria bloquear")
    assert len(paths) == 2


def test_guard_rejects_invalid_pr_number_before_api_lookup(monkeypatch) -> None:
    monkeypatch.setattr(
        guard,
        "github_json",
        lambda *args: (_ for _ in ()).throw(AssertionError("API não deveria ser chamada")),
    )
    try:
        guard.list_pre_pr_runs("owner/repo", "a" * 40, 0, "token")
    except guard.AdmissionGuardError as exc:
        assert str(exc) == "pr_number_invalid"
    else:
        raise AssertionError("número de PR inválido deveria bloquear")


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
        assert "--pr-number" in raw
        assert expected in raw


def test_all_ci_admissions_have_bounded_wait_and_pr_read_access() -> None:
    workflows = (
        (".github/workflows/ci.yml", "  # ─"),
        (".github/workflows/ci-enterprise-fast.yml", "  guardrails:"),
        (".github/workflows/ci-e2e-governado.yml", "  e2e-router:"),
    )
    for path, section_end in workflows:
        raw = (ROOT / path).read_text(encoding="utf-8")
        admission = raw.split("  ci-admission:", 1)[1].split(section_end, 1)[0]
        assert "timeout-minutes: 12" in admission
        assert "--max-wait-seconds 600" in admission
        assert "--poll-seconds 15" in admission
        assert "needs: ci-admission" in raw
        assert "pull-requests: read" in raw




def test_guard_waits_beyond_old_budget_for_matching_pre_pr(monkeypatch) -> None:
    clock = [0.0]
    attempts: list[float] = []
    base = {"base_ref": "main", "base_sha": "b" * 40, "status": "ahead", "behind_by": 0}
    monkeypatch.setattr(guard.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(guard.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(guard, "assert_base_freshness", lambda *args: dict(base))

    def evidence(*args):
        attempts.append(clock[0])
        if clock[0] < 270:
            raise guard.AdmissionGuardError("pre_pr_pending_for_head_sha")
        return {"pre_pr_run_id": 7, "manifest": {"status": "admitted"}}

    monkeypatch.setattr(guard, "verify_evidence", evidence)
    monkeypatch.setattr(
        guard, "github_json",
        lambda repository, path, token: {
            "state": "open", "head": {"sha": "a" * 40}, "base": {"ref": "main"}
        } if path == f"pulls/{PR_NUMBER}" else {},
    )
    result = guard.wait_for_admission("owner/repo", "a" * 40, "main", "token", 600, 15, PR_NUMBER)
    assert result["result"] == "ADMISSION_ACCEPTED"
    assert result["pre_pr_run_id"] == 7
    assert clock[0] == 270
    assert len(attempts) == 19


def test_guard_pending_timeout_remains_fail_closed(monkeypatch) -> None:
    clock = [0.0]
    monkeypatch.setattr(guard.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(guard.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(guard, "assert_base_freshness", lambda *args: {"base_sha": "b" * 40})
    monkeypatch.setattr(
        guard, "verify_evidence",
        lambda *args: (_ for _ in ()).throw(guard.AdmissionGuardError("pre_pr_pending_for_head_sha")),
    )
    try:
        guard.wait_for_admission("owner/repo", "a" * 40, "main", "token", 30, 15, PR_NUMBER)
    except guard.AdmissionGuardError as exc:
        assert str(exc) == "pre_pr_pending_for_head_sha"
    else:
        raise AssertionError("timeout não libera admissão")
    assert clock[0] == 30


def test_guard_rejects_base_change_after_pre_pr_success(monkeypatch) -> None:
    bases = iter(("b" * 40, "c" * 40))
    monkeypatch.setattr(guard, "assert_base_freshness", lambda *args: {"base_sha": next(bases)})
    monkeypatch.setattr(guard, "verify_evidence", lambda *args: {"pre_pr_run_id": 7})
    monkeypatch.setattr(
        guard, "github_json",
        lambda *args: (_ for _ in ()).throw(AssertionError("no PR readback after base drift")),
    )
    try:
        guard.wait_for_admission("owner/repo", "a" * 40, "main", "token", 600, 15, PR_NUMBER)
    except guard.AdmissionGuardError as exc:
        assert str(exc) == "base_changed_while_waiting"
    else:
        raise AssertionError("base nova invalida manifesto antigo")


def test_guard_rejects_changed_pr_revision_on_readback(monkeypatch) -> None:
    monkeypatch.setattr(guard, "assert_base_freshness", lambda *args: {"base_sha": "b" * 40})
    monkeypatch.setattr(guard, "verify_evidence", lambda *args: {"pre_pr_run_id": 7})
    monkeypatch.setattr(
        guard, "github_json",
        lambda repo, path, token: {
            "state": "open", "head": {"sha": "c" * 40}, "base": {"ref": "main"}
        },
    )
    try:
        guard.wait_for_admission("owner/repo", "a" * 40, "main", "token", 600, 15, PR_NUMBER)
    except guard.AdmissionGuardError as exc:
        assert str(exc) == "pr_revision_changed_while_waiting"
    else:
        raise AssertionError("HEAD de outra revisão deve bloquear")


def test_guard_failed_pre_pr_is_not_retried_as_pending(monkeypatch) -> None:
    calls: list[float] = []
    monkeypatch.setattr(guard, "assert_base_freshness", lambda *args: {"base_sha": "b" * 40})
    monkeypatch.setattr(
        guard, "verify_evidence",
        lambda *args: (_ for _ in ()).throw(guard.AdmissionGuardError("pre_pr_failed_for_head_sha")),
    )
    monkeypatch.setattr(guard.time, "sleep", lambda seconds: calls.append(seconds))
    try:
        guard.wait_for_admission("owner/repo", "a" * 40, "main", "token", 600, 15, PR_NUMBER)
    except guard.AdmissionGuardError as exc:
        assert str(exc) == "pre_pr_failed_for_head_sha"
    else:
        raise AssertionError("Pre-PR falho deve bloquear imediatamente")
    assert calls == []


def test_guard_invalid_wait_configuration_blocks_before_api(monkeypatch) -> None:
    monkeypatch.setattr(
        guard, "assert_base_freshness",
        lambda *args: (_ for _ in ()).throw(AssertionError("API must not run")),
    )
    for budget, poll, error in (
        (901, 15, "admission_wait_budget_invalid"),
        (-1, 15, "admission_wait_budget_invalid"),
        (600, 0, "admission_poll_interval_invalid"),
        (600, 61, "admission_poll_interval_invalid"),
    ):
        try:
            guard.wait_for_admission("owner/repo", "a" * 40, "main", "token", budget, poll, PR_NUMBER)
        except guard.AdmissionGuardError as exc:
            assert str(exc) == error
        else:
            raise AssertionError("orçamento de espera inválido deve bloquear")


def test_pr_evidence_gate_requires_manifest_from_current_sha() -> None:
    raw = (ROOT / ".github/workflows/pr-evidence-gate.yml").read_text(encoding="utf-8")
    assert "Pre-PR Readiness Gate" in raw
    assert "Admission manifest missing for current head SHA" in raw
    assert "artifact.name === admissionArtifactName" in raw
    assert "head_sha: headSha" in raw
    assert "Validate admission manifest content" in raw
    assert "scripts.ci_admission_guard" in raw
    assert "pr_number=int(pr_number)" in raw
    enforce = raw.split("- name: Enforce evidence gate result", 1)[1]
    assert 'if [[ "$status" == "passed" ]]' in enforce
    assert '|| "$status" == "deferred"' not in enforce


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


def test_guard_rejects_manifest_missing_workflow_surface_budget() -> None:
    head = "a" * 40
    base = "b" * 40
    payload = manifest.build_manifest(readiness(), head)
    payload["preventive_invariants"] = [
        item for item in payload["preventive_invariants"]
        if item["name"] != "workflow:surface-budget"
    ]
    try:
        guard.validate_manifest_payload(payload, head, base)
    except guard.AdmissionGuardError as exc:
        assert "workflow:surface-budget" in str(exc)
    else:
        raise AssertionError("manifesto sem workflow:surface-budget deveria ser rejeitado")


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
