import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_hitl_approval_decision import build_decision, parse_command


BASE = {
    "issue_number": 1111,
    "issue_url": "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1111",
    "issue_title": "[HITL] Aprovar fluxo",
    "issue_body": "Resumo e evidencias",
    "comment_id": 9001,
    "comment_url": "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1111#issuecomment-9001",
    "actor": "ericson-j-santos",
    "permission": "admin",
    "source_sha": "abcdef1234567890",
    "decided_at": "2026-07-30T12:00:00+00:00",
}


def test_parse_command_requires_supported_command_and_rationale():
    assert parse_command("/approve Evidencias revisadas e aprovadas") == (
        "approve",
        "Evidencias revisadas e aprovadas",
    )
    with pytest.raises(ValueError):
        parse_command("/approve curto")
    with pytest.raises(ValueError):
        parse_command("/unknown justificativa suficientemente longa")


@pytest.mark.parametrize(
    ("command", "status", "next_action"),
    [
        ("/approve Evidencias revisadas e aprovadas", "approved", "rerun_safe_delivery_gates_and_prepare_followup_pr"),
        ("/reject Risco residual nao aceito nesta versao", "rejected", "keep_delivery_blocked_and_close_request"),
        (
            "/adjust Incluir evidencias adicionais do ambiente STG",
            "adjustment_requested",
            "keep_request_open_and_apply_requested_adjustments",
        ),
    ],
)
def test_build_decision_records_authenticated_human(command, status, next_action):
    payload = build_decision(comment_body=command, **BASE)
    assert payload["status"] == status
    assert payload["next_action"] == next_action
    assert payload["approval"]["actor"] == "ericson-j-santos"
    assert payload["request"]["request_sha256"]
    assert len(payload["evidence"]["decision_sha256"]) == 64
    assert payload["production_touched"] is False


def test_build_decision_is_deterministic_with_fixed_timestamp():
    first = build_decision(comment_body="/approve Evidencias revisadas e aprovadas", **BASE)
    second = build_decision(comment_body="/approve Evidencias revisadas e aprovadas", **BASE)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


@pytest.mark.parametrize(
    ("actor", "permission"),
    [
        ("github-actions[bot]", "admin"),
        ("dependabot[bot]", "write"),
        ("external-user", "read"),
    ],
)
def test_build_decision_rejects_bot_or_insufficient_permission(actor, permission):
    with pytest.raises(ValueError):
        build_decision(
            comment_body="/approve Evidencias revisadas e aprovadas",
            **{**BASE, "actor": actor, "permission": permission},
        )
