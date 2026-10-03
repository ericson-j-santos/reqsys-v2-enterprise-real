#!/usr/bin/env python3
"""Plan idempotent GitHub issue synchronization for real BACEN formal actions."""
from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MARKER_RE = re.compile(r"<!--\s*reqsys-bacen-control:([A-Z0-9-]+)\s*-->")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def marker(control_id: str) -> str:
    return f"<!-- reqsys-bacen-control:{control_id} -->"


def normalize_labels(issue: dict[str, Any]) -> list[str]:
    labels = issue.get("labels") or []
    normalized: list[str] = []
    for label in labels:
        if isinstance(label, str):
            normalized.append(label)
        elif isinstance(label, dict) and label.get("name"):
            normalized.append(str(label["name"]))
    return sorted(set(normalized))


def labels_for(item: dict[str, Any]) -> list[str]:
    priority = str(item.get("priority") or "P3").lower()
    role = str(item.get("responsible_role") or "unassigned-role").lower().replace("_", "-")
    return sorted({"bacen", "formal-action", f"priority-{priority}", f"owner-{role}"})


def title_for(item: dict[str, Any]) -> str:
    control_id = str(item["control_id"])
    priority = str(item.get("priority") or "P3")
    title = str(item.get("title") or "Ação formal pendente")
    return f"[BACEN][{priority}] {control_id} — {title}"


def body_for(item: dict[str, Any]) -> str:
    control_id = str(item["control_id"])
    return "\n".join(
        [
            marker(control_id),
            f"# Ação formal pendente — {control_id}",
            "",
            "Esta issue é mantida automaticamente pelo ReqSys enquanto existir ação humana formal ativa para o estágio atual.",
            "",
            "## Estado evidenciado",
            "",
            f"- Status do controle: `{item.get('status')}`",
            f"- Prioridade: `{item.get('priority')}`",
            f"- Papel responsável: `{item.get('responsible_role') or 'não definido'}`",
            f"- Ação requerida: `{item.get('required_action') or 'não definida'}`",
            f"- Evidência esperada: `{item.get('evidence_reference') or 'não definida'}`",
            f"- Lifecycle: `{item.get('lifecycle_stage') or 'não definido'}`",
            "",
            "## Campos que exigem informação real",
            "",
            "- Responsável pessoal: **não atribuído pela automação**",
            "- Prazo institucional: **não inventado pela automação**",
            "- Aprovação/assinatura: **pendente de autoridade real**",
            "",
            "## Critério de encerramento",
            "",
            "A issue será encerrada quando a ação deixar de ser ativa: por implementação formal do controle ou por diferimento explícito para um gate institucional posterior.",
            "",
            "`production_touched=false`",
            "",
        ]
    )


def deferred_title_for(item: dict[str, Any]) -> str:
    control_id = str(item["control_id"])
    return f"[{control_id}][DEFERRED] Ação formal — reativar no gate institucional"


def deferred_body_for(item: dict[str, Any]) -> str:
    control_id = str(item["control_id"])
    gate = str(item.get("institutional_gate_stage") or "PRODUCTION")
    return "\n".join(
        [
            marker(control_id),
            f"# {control_id} — ação formal diferida pelo ciclo de vida",
            "",
            "A ação humana formal deste controle não está ativa enquanto o ReqSys permanecer em desenvolvimento interno/pré-oficialização.",
            "",
            "## Estado evidenciado",
            "",
            f"- Status do controle: `{item.get('status')}`",
            f"- Lifecycle: `{item.get('lifecycle_stage') or 'não definido'}`",
            "- Governança institucional: `deferred_until_institutionalization`",
            f"- Gate de reativação: `{gate}`",
            f"- Próxima ação técnica: `{item.get('required_action') or 'não definida'}`",
            f"- Evidência esperada: `{item.get('evidence_reference') or 'não definida'}`",
            "- Produção: `production_touched=false`",
            "",
            "## Decisão operacional",
            "",
            "A ausência atual de aprovação, revisão, assinatura ou evidência institucional real não deve gerar dado fabricado nem ação humana imediata. O controle mantém seu status regulatório atual e será reavaliado no gate institucional.",
            "",
            "## Reativação futura",
            "",
            f"Ao alcançar `{gate}` ou outro estágio institucional equivalente, reativar a ação formal e exigir as evidências reais definidas pelo controle.",
            "",
            "Encerramento atual significa **ação formal diferida**, não controle `implemented` e não conformidade institucional declarada.",
            "",
        ]
    )


def issue_control_id(issue: dict[str, Any]) -> str | None:
    body = str(issue.get("body") or "")
    match = MARKER_RE.search(body)
    return match.group(1) if match else None


def build_plan(backlog: dict[str, Any], existing_issues: list[dict[str, Any]]) -> dict[str, Any]:
    items = backlog.get("items") or []
    deferred_items = backlog.get("deferred_items") or []
    if not isinstance(items, list):
        raise ValueError("backlog items must be a list")
    if not isinstance(deferred_items, list):
        raise ValueError("backlog deferred_items must be a list")
    if not isinstance(existing_issues, list):
        raise ValueError("existing issues must be a list")

    by_control: dict[str, list[dict[str, Any]]] = {}
    for issue in existing_issues:
        if not isinstance(issue, dict):
            continue
        control_id = issue_control_id(issue)
        if control_id:
            by_control.setdefault(control_id, []).append(issue)

    operations: list[dict[str, Any]] = []
    pending_ids: set[str] = set()
    deferred_ids: set[str] = set()

    for item in items:
        if not isinstance(item, dict) or not item.get("control_id"):
            continue
        control_id = str(item["control_id"])
        pending_ids.add(control_id)
        expected_title = title_for(item)
        expected_body = body_for(item)
        expected_labels = labels_for(item)
        candidates = sorted(
            by_control.get(control_id, []),
            key=lambda issue: (str(issue.get("state") or "") != "open", -int(issue.get("number") or 0)),
        )
        current = candidates[0] if candidates else None

        if current is None:
            operations.append(
                {
                    "action": "create",
                    "control_id": control_id,
                    "title": expected_title,
                    "body": expected_body,
                    "labels": expected_labels,
                }
            )
            continue

        needs_update = (
            str(current.get("title") or "") != expected_title
            or str(current.get("body") or "") != expected_body
            or normalize_labels(current) != expected_labels
            or str(current.get("state") or "").lower() != "open"
        )
        if needs_update:
            operations.append(
                {
                    "action": "update",
                    "number": int(current["number"]),
                    "control_id": control_id,
                    "title": expected_title,
                    "body": expected_body,
                    "labels": expected_labels,
                    "state": "open",
                }
            )

        for duplicate in candidates[1:]:
            if str(duplicate.get("state") or "").lower() == "open":
                operations.append(
                    {
                        "action": "close",
                        "number": int(duplicate["number"]),
                        "control_id": control_id,
                        "comment": "Fechada automaticamente por duplicidade; a issue canônica permanece aberta.",
                    }
                )

    for item in deferred_items:
        if not isinstance(item, dict) or not item.get("control_id"):
            continue
        control_id = str(item["control_id"])
        deferred_ids.add(control_id)
        candidates = sorted(
            by_control.get(control_id, []),
            key=lambda issue: (str(issue.get("state") or "") == "open", int(issue.get("number") or 0)),
            reverse=True,
        )
        if not candidates:
            continue

        current = candidates[0]
        expected_title = deferred_title_for(item)
        expected_body = deferred_body_for(item)
        expected_labels = labels_for(item)
        needs_defer = (
            str(current.get("title") or "") != expected_title
            or str(current.get("body") or "") != expected_body
            or normalize_labels(current) != expected_labels
            or str(current.get("state") or "").lower() != "closed"
        )
        if needs_defer:
            operations.append(
                {
                    "action": "defer",
                    "number": int(current["number"]),
                    "control_id": control_id,
                    "title": expected_title,
                    "body": expected_body,
                    "labels": expected_labels,
                    "comment": (
                        "Ação formal diferida pelo lifecycle atual; reativar no gate "
                        f"{item.get('institutional_gate_stage') or 'PRODUCTION'}. "
                        "O controle não foi promovido para `implemented`."
                    ),
                }
            )

        for duplicate in candidates[1:]:
            if str(duplicate.get("state") or "").lower() == "open":
                operations.append(
                    {
                        "action": "close",
                        "number": int(duplicate["number"]),
                        "control_id": control_id,
                        "comment": "Fechada automaticamente por duplicidade de ação formal diferida.",
                    }
                )

    for control_id, issues in by_control.items():
        if control_id in pending_ids or control_id in deferred_ids:
            continue
        for issue in issues:
            if str(issue.get("state") or "").lower() == "open":
                operations.append(
                    {
                        "action": "close",
                        "number": int(issue["number"]),
                        "control_id": control_id,
                        "comment": "Controle marcado como `implemented`; issue formal encerrada automaticamente.",
                    }
                )

    action_counts = {
        action: sum(op["action"] == action for op in operations)
        for action in ("create", "update", "defer", "close")
    }
    return {
        "schema_version": "1.1.0",
        "contract": "reqsys-bacen-human-action-issue-sync",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "idempotent_issue_sync",
        "pending_controls": len(pending_ids),
        "deferred_controls": len(deferred_ids),
        "operations": operations,
        "summary": {**action_counts, "total_operations": len(operations)},
        "personal_assignees_fabricated": False,
        "due_dates_fabricated": False,
        "approvals_fabricated": False,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backlog", type=Path, required=True)
    parser.add_argument("--issues", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = build_plan(load_json(args.backlog), load_json(args.issues))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
