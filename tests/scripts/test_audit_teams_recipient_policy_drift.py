from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_teams_recipient_policy_drift import audit


def _write_config(path: Path, policies: list[dict], schema_version: str = "1.0.0") -> None:
    path.write_text(
        json.dumps({"schema_version": schema_version, "policies": policies}),
        encoding="utf-8",
    )


def _policy(name: str, destination: str = "owner@example.com") -> dict:
    return {
        "name": name,
        "delivery_mode": "all",
        "recipients": [
            {
                "name": "Owner",
                "destination_id": destination,
                "destination_type": "chat",
                "priority": 10,
                "active": True,
            }
        ],
    }


def _runtime_policy(name: str) -> dict:
    return {
        "name": name,
        "delivery_mode": "all",
        "recipient_source": "runtime_db",
        "recipients": [],
    }


def test_audit_passa_sem_reproduzir_destino_no_relatorio(tmp_path: Path) -> None:
    config = tmp_path / "policies.json"
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _write_config(config, [_policy("hitl-approvers"), _policy("reqsys-operations")])
    (workflows / "hitl.yml").write_text(
        "env:\n  HITL_RECIPIENT_POLICY: hitl-approvers\n",
        encoding="utf-8",
    )
    (workflows / "logs.yml").write_text(
        "env:\n  TEAMS_RECIPIENT_POLICY: reqsys-operations\n",
        encoding="utf-8",
    )

    report = audit(config, workflows)

    assert report["result"] == "pass"
    assert report["summary"]["configured_policies"] == 2
    serialized = json.dumps(report)
    assert "owner@example.com" not in serialized
    assert report["sensitive_destinations_exposed"] is True


def test_audit_accepts_runtime_managed_policies_without_inline_identity(tmp_path: Path) -> None:
    config = tmp_path / "policies.json"
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _write_config(
        config,
        [_runtime_policy("hitl-approvers"), _runtime_policy("reqsys-operations")],
        schema_version="1.1.0",
    )
    (workflows / "hitl.yml").write_text(
        "env:\n  HITL_RECIPIENT_POLICY: hitl-approvers\n",
        encoding="utf-8",
    )
    (workflows / "logs.yml").write_text(
        "env:\n  TEAMS_RECIPIENT_POLICY: reqsys-operations\n",
        encoding="utf-8",
    )

    report = audit(config, workflows)

    assert report["result"] == "pass"
    assert report["summary"]["runtime_managed_policies"] == 2
    assert report["summary"]["inline_destination_count"] == 0
    assert report["sensitive_destinations_exposed"] is False


def test_audit_bloqueia_identidade_inline_em_politica_runtime(tmp_path: Path) -> None:
    config = tmp_path / "policies.json"
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    policy = _runtime_policy("hitl-approvers")
    policy["recipients"].append(
        {
            "name": "Owner",
            "destination_id": "owner@example.com",
            "destination_type": "chat",
            "active": True,
        }
    )
    _write_config(config, [policy], schema_version="1.1.0")
    (workflows / "hitl.yml").write_text(
        "env:\n  HITL_RECIPIENT_POLICY: hitl-approvers\n",
        encoding="utf-8",
    )

    report = audit(config, workflows)

    assert report["result"] == "fail"
    assert (
        "runtime_managed_policy_has_inline_recipients:hitl-approvers"
        in report["errors"]
    )


def test_audit_bloqueia_politica_referenciada_nao_configurada(tmp_path: Path) -> None:
    config = tmp_path / "policies.json"
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _write_config(config, [_policy("hitl-approvers")])
    (workflows / "logs.yml").write_text(
        "env:\n  TEAMS_RECIPIENT_POLICY: reqsys-operations\n",
        encoding="utf-8",
    )

    report = audit(config, workflows)

    assert report["result"] == "fail"
    assert "referenced_policy_not_configured:reqsys-operations" in report["errors"]


def test_audit_bloqueia_destino_duplicado_e_sem_ativos(tmp_path: Path) -> None:
    config = tmp_path / "policies.json"
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    policy = _policy("hitl-approvers")
    policy["recipients"][0]["active"] = False
    policy["recipients"].append(dict(policy["recipients"][0]))
    _write_config(config, [policy])
    (workflows / "hitl.yml").write_text(
        "env:\n  HITL_RECIPIENT_POLICY: hitl-approvers\n",
        encoding="utf-8",
    )

    report = audit(config, workflows)

    assert report["result"] == "fail"
    assert "duplicate_destination:hitl-approvers" in report["errors"]
    assert "policy_without_active_recipients:hitl-approvers" in report["errors"]
