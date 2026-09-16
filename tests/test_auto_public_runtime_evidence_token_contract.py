"""Contract tests for the governed credential of Auto Public Runtime Evidence (P0-B).

The workflow used to consume the long-lived ``GH_PAT_ACTIONS`` secret directly.
It must now mint an ephemeral GitHub App installation token, fail closed when
the governed identity is incomplete, and prove the credential with an
authenticated read before any dispatch.
"""

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
def steps(raw: str) -> list[dict]:
    document = yaml.safe_load(raw)
    jobs = document["jobs"]
    assert len(jobs) == 1, "contrato assume um único job"
    job = next(iter(jobs.values()))
    return job["steps"]


def _step(steps: list[dict], name_fragment: str) -> dict:
    matches = [item for item in steps if name_fragment in str(item.get("name", ""))]
    assert matches, f"passo ausente: {name_fragment}"
    return matches[0]


def test_legacy_pat_is_not_referenced(raw: str) -> None:
    assert "GH_PAT_ACTIONS" not in raw


def test_ephemeral_app_token_is_minted_with_least_privilege(steps: list[dict]) -> None:
    step = _step(steps, "Emitir token efêmero")

    assert step["uses"].startswith("actions/create-github-app-token@")
    with_block = step["with"]
    assert with_block["app-id"] == "${{ vars.REQSYS_STACK_REBASE_APP_ID }}"
    assert with_block["private-key"] == (
        "${{ secrets.REQSYS_STACK_REBASE_PRIVATE_KEY }}"
    )
    assert with_block["repositories"] == "reqsys-v2-enterprise-real"
    # dispatch exige actions:write; nada além de leitura de conteúdo é concedido
    assert with_block["permission-actions"] == "write"
    assert with_block["permission-contents"] == "read"
    assert not any(
        key.startswith("permission-") and value == "write"
        for key, value in with_block.items()
        if key != "permission-actions"
    )


def test_missing_identity_fails_closed(steps: list[dict]) -> None:
    step = _step(steps, "Validar pré-condição da identidade governada")
    body = step["run"]

    assert "vars.REQSYS_STACK_REBASE_APP_ID" in body
    assert "secrets.REQSYS_STACK_REBASE_PRIVATE_KEY" in body
    assert "exit 1" in body
    assert "set -euo pipefail" in body


def test_invalid_credential_is_detected_before_dispatch(steps: list[dict]) -> None:
    names = [str(item.get("name", "")) for item in steps]
    probe_index = next(
        index for index, name in enumerate(names) if "Provar token" in name
    )
    dispatch_index = next(
        index for index, name in enumerate(names) if "Dispatch Public Runtime" in name
    )
    assert probe_index < dispatch_index, "a prova do token deve preceder o dispatch"

    probe = steps[probe_index]
    assert probe["env"]["GH_TOKEN"] == "${{ steps.app-token.outputs.token }}"
    body = probe["run"]
    assert "gh api" in body, "a prova precisa de leitura autenticada independente"
    assert "public-runtime-evidence.yml" in body
    assert "exit 1" in body


def test_every_gh_token_comes_from_the_ephemeral_step(steps: list[dict]) -> None:
    tokens = [
        item["env"]["GH_TOKEN"]
        for item in steps
        if isinstance(item.get("env"), dict) and "GH_TOKEN" in item["env"]
    ]
    assert tokens, "nenhum passo autenticado encontrado"
    assert all(value == "${{ steps.app-token.outputs.token }}" for value in tokens)


def test_no_secret_value_is_echoed(steps: list[dict]) -> None:
    for step in steps:
        body = str(step.get("run", ""))
        assert "echo \"${GOVERNED_APP_PRIVATE_KEY" not in body
        assert "echo $GH_TOKEN" not in body
        assert "echo \"${GH_TOKEN" not in body
