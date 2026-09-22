from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ollama-ci-triage.yml"
POLICY = ROOT / ".github/self-hosted-runner-policy.json"
SCRIPT = ROOT / "scripts/ollama_ci_triage.py"


def test_workflow_is_event_driven_and_non_recursive() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_run:" in raw
    assert "workflow_dispatch:" in raw
    assert "schedule:" not in raw
    watched = raw.split("workflows:", 1)[1].split("types:", 1)[0]
    assert "Ollama CI Triage" not in watched
    assert "CI — ReqSys v2 Enterprise" in watched
    assert "CI Enterprise Fast" in watched
    assert "Pre-PR Readiness Gate" in watched
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw


def test_automatic_path_checks_out_only_trusted_control_plane() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.repository.default_branch" in raw
    assert "github.event.workflow_run.head_sha" not in raw
    assert "persist-credentials: false" in raw
    assert "pull_request_target:" not in raw


def test_permissions_and_endpoints_are_restricted() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "actions: read" in raw
    assert "contents: read" in raw
    assert "issues: write" in raw
    assert "contents: write" not in raw
    assert "actions: write" not in raw
    assert "secrets." not in raw
    assert "http://127.0.0.1:11434" in raw
    assert "http://127.0.0.1:8097" in raw


def test_script_has_deterministic_escalation_guards() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")
    assert "TECHNICAL_CATEGORIES" in raw
    assert "CONFIDENCE_THRESHOLD = 0.75" in raw
    assert "external_fork_blocked" in raw
    assert "stale_ci_sha" in raw
    assert '"target_branch": target_branch' in raw
    assert "subprocess" not in raw


def test_self_hosted_workflow_is_allowlisted() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["self_hosted_allowed"] is True
    assert ".github/workflows/ollama-ci-triage.yml" in policy["approved_workflows"]
    assert policy["required_adr"]
