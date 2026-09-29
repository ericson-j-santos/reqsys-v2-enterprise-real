"""Contract tests for PC24x7-only Auto Public Runtime Evidence routing."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "auto-public-runtime-evidence.yml"


@pytest.fixture(scope="module")
def raw() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def document(raw: str) -> dict:
    return yaml.safe_load(raw)


@pytest.fixture(scope="module")
def steps(document: dict) -> list[dict]:
    jobs = document["jobs"]
    assert len(jobs) == 1, "contrato assume um único job"
    job = next(iter(jobs.values()))
    return job["steps"]


def _step(steps: list[dict], name_fragment: str) -> dict:
    matches = [item for item in steps if name_fragment in str(item.get("name", ""))]
    assert matches, f"passo ausente: {name_fragment}"
    return matches[0]


def test_blocking_main_post_merge_is_the_automatic_upstream(raw: str) -> None:
    assert "Main Post-Merge Validation" in raw
    assert "Fly Automatic Environment Promotion" not in raw
    assert "ReqSys Fly Runtime P0" not in raw


def test_automatic_trigger_requires_blocking_dispatch_event(steps: list[dict]) -> None:
    resolver = _step(steps, "Resolve trigger context")
    body = resolver["run"]
    assert "github.event.workflow_run.conclusion" in body
    assert "github.event.workflow_run.head_branch" in body
    assert "github.event.workflow_run.event" in body
    assert '"workflow_dispatch"' in body


def test_long_lived_or_app_credentials_are_not_referenced(raw: str) -> None:
    assert "GH_PAT_ACTIONS" not in raw
    assert "REQSYS_STACK_REBASE_APP_ID" not in raw
    assert "REQSYS_STACK_REBASE_PRIVATE_KEY" not in raw
    assert "create-github-app-token" not in raw


def test_native_token_has_only_required_permissions(document: dict) -> None:
    permissions = document["permissions"]
    assert permissions == {
        "actions": "write",
        "contents": "read",
    }


def test_automatic_inputs_use_signed_pc24x7_locator_without_static_fallback(raw: str, steps: list[dict]) -> None:
    locator = _step(steps, "Resolve signed PC24x7 DEV locator")
    assert "resolve_pc24x7_dev_locator.mjs --self-test" in locator["run"]
    assert "resolve_pc24x7_dev_locator.mjs --output" in locator["run"]

    resolver = _step(steps, "Resolve inputs")
    body = resolver["run"]
    assert "LOCATOR_BASE_URL" in resolver["env"]
    assert "https://*.trycloudflare.com" in body
    assert "Runtime DEV legado Fly.io rejeitado" in body
    assert 'echo "strict=true"' in body
    assert 'echo "provider=pc24x7"' in body

    assert "REQSYS_DEV_RUNTIME_PROVIDER" not in raw
    assert "PC24X7_DEV_BASE_URL" not in raw
    assert "PC24X7_DEV_FRONTEND_URL" not in raw
    assert "reqsys-api.fly.dev" not in raw


def test_native_token_is_proved_before_dispatch(steps: list[dict]) -> None:
    names = [str(item.get("name", "")) for item in steps]
    probe_index = next(index for index, name in enumerate(names) if "Provar token efêmero nativo" in name)
    dispatch_index = next(index for index, name in enumerate(names) if "Dispatch Public Runtime" in name)
    assert probe_index < dispatch_index

    probe = steps[probe_index]
    assert probe["env"]["GH_TOKEN"] == "${{ github.token }}"
    body = probe["run"]
    assert "gh api" in body
    assert "public-runtime-evidence.yml" in body
    assert "exit 1" in body


def test_every_authenticated_gh_call_uses_native_token(steps: list[dict]) -> None:
    tokens = [
        item["env"]["GH_TOKEN"]
        for item in steps
        if isinstance(item.get("env"), dict) and "GH_TOKEN" in item["env"]
    ]
    assert tokens
    assert all(value == "${{ github.token }}" for value in tokens)


def test_dispatch_contract_is_preserved(steps: list[dict]) -> None:
    dispatch = _step(steps, "Dispatch Public Runtime")
    body = dispatch["run"]

    assert "gh workflow run public-runtime-evidence.yml" in body
    assert '--ref "${TARGET_REF}"' in body
    assert "public_url=${PUBLIC_URL}" in body
    assert "strict=${STRICT}" in body
    assert "publish_comment=${PUBLISH_COMMENT}" in body
    assert "issue_number=${ISSUE_NUMBER}" in body


def test_no_token_value_is_echoed(steps: list[dict]) -> None:
    for step in steps:
        body = str(step.get("run", ""))
        assert "echo $GH_TOKEN" not in body
        assert 'echo "${GH_TOKEN' not in body
