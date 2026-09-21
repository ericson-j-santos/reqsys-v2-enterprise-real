#!/usr/bin/env python3
"""Inventário de required status checks versus workflows reais do repositório.

Cruza os contextos exigidos na branch protection (payload real quando disponível)
e os contextos declarados na linha base versionada com os contextos que os
workflows do repositório podem efetivamente produzir, classificando cada
exigência antes de qualquer alteração de proteção de branch.

Fecha o gap canônico `OPS-GAP-GITOPS-CHECKS-001`: required check inexistente,
renomeado ou nunca materializado deixa PR travado em `Expected — Waiting for
status to be reported`.

Leitura pura: não chama API, não altera branch protection e não toca produção.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.evaluate_required_checks_materialization import (  # noqa: E402
    required_contexts as protection_required_contexts,
)

CONTRACT = "reqsys-required-checks-stale-inventory"
SCHEMA_VERSION = "1.0.0"
DEFAULT_WORKFLOW_DIR = Path(".github/workflows")
DEFAULT_POLICY = Path("config/required-checks-inventory-policy.json")
DEFAULT_OUTPUT = Path("artifacts/required-checks-stale-inventory/report.json")
DEFAULT_MARKDOWN = Path("artifacts/required-checks-stale-inventory/report.md")
CLOSE_MATCH_CUTOFF = 0.82
EXPRESSION_RE = re.compile(r"\$\{\{.*?\}\}")

STATUS_ACTIVE = "active"
STATUS_CONDITIONAL_RISK = "conditional_risk"
STATUS_NOT_PR_TRIGGERED = "not_pr_triggered"
STATUS_WORKFLOW_NAME_MISMATCH = "workflow_name_mismatch"
STATUS_RENAMED_CANDIDATE = "renamed_candidate"
STATUS_STALE = "stale"
BLOCKING_STATUSES = frozenset(
    {
        STATUS_CONDITIONAL_RISK,
        STATUS_NOT_PR_TRIGGERED,
        STATUS_WORKFLOW_NAME_MISMATCH,
        STATUS_RENAMED_CANDIDATE,
        STATUS_STALE,
    }
)
MISSING_STATUSES = frozenset(
    {STATUS_WORKFLOW_NAME_MISMATCH, STATUS_RENAMED_CANDIDATE, STATUS_STALE}
)
VALID_DECISIONS = frozenset({"keep", "rename", "remove"})


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", str(text))
    ascii_text = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", ascii_text.casefold()).split())


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    raw = workflow.get("on", workflow.get(True))
    if isinstance(raw, dict):
        return {str(key): value for key, value in raw.items()}
    if isinstance(raw, list):
        return {str(item): None for item in raw}
    if isinstance(raw, str):
        return {raw: None}
    return {}


def _pull_request_eligibility(triggers: dict[str, Any], target_branch: str) -> dict[str, Any]:
    if "pull_request" not in triggers:
        return {"pr_triggered": False, "branch_eligible": False, "path_filtered": False}
    config = triggers.get("pull_request")
    config = config if isinstance(config, dict) else {}
    branches = config.get("branches")
    branches_ignore = config.get("branches-ignore")
    branch_eligible = True
    if isinstance(branches, list) and branches:
        branch_eligible = any(_branch_matches(str(pattern), target_branch) for pattern in branches)
    if isinstance(branches_ignore, list) and branches_ignore:
        branch_eligible = branch_eligible and not any(
            _branch_matches(str(pattern), target_branch) for pattern in branches_ignore
        )
    return {
        "pr_triggered": True,
        "branch_eligible": branch_eligible,
        "path_filtered": bool(config.get("paths") or config.get("paths-ignore")),
    }


def _branch_matches(pattern: str, branch: str) -> bool:
    if pattern == branch:
        return True
    if pattern.endswith("**"):
        return branch.startswith(pattern[:-2])
    if pattern.endswith("*"):
        return branch.startswith(pattern[:-1])
    return False


def _job_producers(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    producers: list[dict[str, Any]] = []
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return producers
    for job_id, raw_job in jobs.items():
        job = raw_job if isinstance(raw_job, dict) else {}
        declared_name = job.get("name")
        context = str(declared_name) if declared_name else str(job_id)
        condition = str(job.get("if") or "")
        strategy = job.get("strategy") if isinstance(job.get("strategy"), dict) else {}
        producers.append(
            {
                "job_id": str(job_id),
                "context": context,
                "dynamic_name": bool(EXPRESSION_RE.search(context)),
                "matrix": bool(strategy.get("matrix")),
                "reusable_call": bool(job.get("uses")),
                "always_reports": (not condition) or ("always()" in condition),
                "conditional": bool(condition) and "always()" not in condition,
            }
        )
    return producers


def parse_workflow(path: Path, *, target_branch: str) -> dict[str, Any] | None:
    import yaml  # noqa: PLC0415 — dependência só necessária ao varrer workflows

    try:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return {"file": path.name, "unparsed": True, "reason": str(exc)[:200], "producers": []}
    if not isinstance(workflow, dict):
        return {"file": path.name, "unparsed": True, "reason": "root is not a mapping", "producers": []}

    triggers = _triggers(workflow)
    eligibility = _pull_request_eligibility(triggers, target_branch)
    return {
        "file": path.name,
        "name": str(workflow.get("name") or path.stem),
        "triggers": sorted(triggers),
        "unparsed": False,
        **eligibility,
        "producers": _job_producers(workflow),
    }


def build_workflow_inventory(workflow_dir: Path, *, target_branch: str) -> dict[str, Any]:
    workflows: list[dict[str, Any]] = []
    for path in sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]):
        parsed = parse_workflow(path, target_branch=target_branch)
        if parsed:
            workflows.append(parsed)

    context_index: dict[str, list[dict[str, Any]]] = {}
    workflow_name_index: dict[str, list[dict[str, Any]]] = {}
    for workflow in workflows:
        if workflow["unparsed"]:
            continue
        workflow_name_index.setdefault(workflow["name"], []).append(workflow)
        for producer in workflow["producers"]:
            context_index.setdefault(producer["context"], []).append(
                {
                    **producer,
                    "workflow": workflow["name"],
                    "file": workflow["file"],
                    "pr_triggered": workflow["pr_triggered"],
                    "branch_eligible": workflow["branch_eligible"],
                    "path_filtered": workflow["path_filtered"],
                }
            )
    return {
        "workflows": workflows,
        "context_index": context_index,
        "workflow_name_index": workflow_name_index,
        "unparsed_files": [w["file"] for w in workflows if w["unparsed"]],
    }


def _producer_reference(producer: dict[str, Any]) -> str:
    return f"{producer['workflow']} :: {producer['job_id']}"


def _risk_reasons(producer: dict[str, Any]) -> list[str]:
    reasons = []
    if producer["path_filtered"]:
        reasons.append("workflow_path_filtered")
    if producer["conditional"]:
        reasons.append("job_conditional_without_always")
    if producer["matrix"]:
        reasons.append("matrix_job_suffixes_context")
    if producer["dynamic_name"]:
        reasons.append("dynamic_job_name")
    if producer["reusable_call"]:
        reasons.append("reusable_workflow_call_prefixes_context")
    return reasons


def _suggestions(producers: list[dict[str, Any]]) -> list[str]:
    active = [p["context"] for p in producers if p["pr_triggered"] and p["branch_eligible"] and not p["path_filtered"] and p["always_reports"]]
    return sorted(dict.fromkeys(active or [p["context"] for p in producers]))


def classify_context(context: str, inventory: dict[str, Any]) -> dict[str, Any]:
    producers = inventory["context_index"].get(context, [])
    if producers:
        pr_producers = [p for p in producers if p["pr_triggered"] and p["branch_eligible"]]
        safe = [
            p
            for p in pr_producers
            if not p["path_filtered"] and p["always_reports"] and not p["matrix"] and not p["dynamic_name"] and not p["reusable_call"]
        ]
        if safe:
            return {
                "context": context,
                "status": STATUS_ACTIVE,
                "producers": [_producer_reference(p) for p in safe],
                "reasons": [],
                "suggested_contexts": [],
            }
        if pr_producers:
            reasons = sorted({reason for p in pr_producers for reason in _risk_reasons(p)})
            return {
                "context": context,
                "status": STATUS_CONDITIONAL_RISK,
                "producers": [_producer_reference(p) for p in pr_producers],
                "reasons": reasons,
                "suggested_contexts": [],
            }
        return {
            "context": context,
            "status": STATUS_NOT_PR_TRIGGERED,
            "producers": [_producer_reference(p) for p in producers],
            "reasons": ["no_pull_request_trigger_for_target_branch"],
            "suggested_contexts": [],
        }

    matching_workflows = inventory["workflow_name_index"].get(context)
    if matching_workflows:
        job_producers = [
            {**producer, "workflow": workflow["name"], "file": workflow["file"], "pr_triggered": workflow["pr_triggered"], "branch_eligible": workflow["branch_eligible"], "path_filtered": workflow["path_filtered"]}
            for workflow in matching_workflows
            for producer in workflow["producers"]
        ]
        return {
            "context": context,
            "status": STATUS_WORKFLOW_NAME_MISMATCH,
            "producers": [],
            "reasons": ["context_matches_workflow_name_not_check_run_name"],
            "suggested_contexts": _suggestions(job_producers),
        }

    normalized_index = {normalize(key): key for key in inventory["context_index"]}
    close = difflib.get_close_matches(normalize(context), list(normalized_index), n=3, cutoff=CLOSE_MATCH_CUTOFF)
    if close:
        return {
            "context": context,
            "status": STATUS_RENAMED_CANDIDATE,
            "producers": [],
            "reasons": ["no_exact_check_run_name_but_close_match_found"],
            "suggested_contexts": [normalized_index[item] for item in close],
        }
    return {
        "context": context,
        "status": STATUS_STALE,
        "producers": [],
        "reasons": ["no_workflow_produces_this_check_run_name"],
        "suggested_contexts": [],
    }


def normalize_decisions(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for raw in policy.get("decisions") or []:
        if not isinstance(raw, dict):
            continue
        context = str(raw.get("context") or "").strip()
        decision = str(raw.get("decision") or "").strip()
        if not context or decision not in VALID_DECISIONS:
            continue
        decisions[context] = {
            "decision": decision,
            "target_contexts": [str(item) for item in (raw.get("target_contexts") or [])],
            "rationale": str(raw.get("rationale") or ""),
            "owner": str(raw.get("owner") or ""),
            "decided_at": str(raw.get("decided_at") or ""),
        }
    return decisions


def resolve_declared_contexts(
    *, policy: dict[str, Any], protection_payload: dict[str, Any] | None
) -> tuple[list[str], str]:
    if protection_payload is None:
        source = "versioned_baseline"
        contexts = [str(item) for item in policy.get("declared_required_contexts") or []]
    elif protection_payload.get("unavailable"):
        source = "versioned_baseline_protection_unavailable"
        contexts = [str(item) for item in policy.get("declared_required_contexts") or []]
    else:
        source = "branch_protection_api"
        contexts = protection_required_contexts(protection_payload)
    return sorted(dict.fromkeys(context.strip() for context in contexts if context.strip())), source


def resolve_decision(report_decision_inputs: dict[str, Any]) -> str:
    if report_decision_inputs["inconclusive"]:
        return "no_required_contexts_declared"
    statuses = report_decision_inputs["statuses"]
    if statuses & MISSING_STATUSES:
        return "stale_or_misnamed_required_checks_detected"
    if statuses & BLOCKING_STATUSES:
        return "materialization_risk_detected"
    if not report_decision_inputs["recommended_all_active"]:
        return "recommended_contexts_not_materialized"
    return "required_checks_aligned"


def build_report(
    *,
    policy: dict[str, Any],
    inventory: dict[str, Any],
    protection_payload: dict[str, Any] | None = None,
    target_branch: str = "main",
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    declared, source = resolve_declared_contexts(policy=policy, protection_payload=protection_payload)
    decisions = normalize_decisions(policy)

    classifications = []
    for context in declared:
        classification = classify_context(context, inventory)
        classification["registered_decision"] = decisions.get(context)
        classification["decision_required"] = classification["status"] in BLOCKING_STATUSES
        classifications.append(classification)

    recommended = sorted(
        dict.fromkeys(str(item).strip() for item in policy.get("recommended_required_contexts") or [] if str(item).strip())
    )
    recommended_validation = [classify_context(context, inventory) for context in recommended]
    recommended_all_active = all(item["status"] == STATUS_ACTIVE for item in recommended_validation) if recommended_validation else False

    pending_decisions = [
        item["context"] for item in classifications if item["decision_required"] and not item["registered_decision"]
    ]
    stale_contexts = [item["context"] for item in classifications if item["status"] in MISSING_STATUSES]
    by_status: dict[str, int] = {}
    for item in classifications:
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1

    inconclusive = not declared
    decision = resolve_decision(
        {
            "inconclusive": inconclusive,
            "statuses": {item["status"] for item in classifications},
            "recommended_all_active": recommended_all_active,
        }
    )
    observed = (observed_at or datetime.now(UTC)).astimezone(UTC)
    blocking = bool(inconclusive or pending_decisions or not recommended_all_active)

    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "observed_at": observed.isoformat(),
        "target_branch": target_branch,
        "gap_reference": policy.get("gap_reference") or "OPS-GAP-GITOPS-CHECKS-001",
        "required_contexts_source": source,
        "decision": decision,
        "inconclusive": inconclusive,
        "blocking": blocking,
        "summary": {
            "declared_context_count": len(declared),
            "producible_context_count": len(inventory["context_index"]),
            "workflow_count": len([w for w in inventory["workflows"] if not w["unparsed"]]),
            "unparsed_workflow_files": inventory["unparsed_files"],
            "by_status": dict(sorted(by_status.items())),
            "stale_contexts": stale_contexts,
            "pending_decisions": pending_decisions,
            "recommended_all_active": recommended_all_active,
        },
        "classifications": classifications,
        "recommended_validation": recommended_validation,
        "automatic_branch_protection_change_allowed": False,
        "automatic_context_removal_allowed": False,
        "production_touched": False,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Required Checks Stale Inventory",
        "",
        f"- Contrato: `{report['contract']}` (schema `{report['schema_version']}`)",
        f"- Observado em: `{report['observed_at']}`",
        f"- Branch alvo: `{report['target_branch']}`",
        f"- Gap canônico: `{report['gap_reference']}`",
        f"- Fonte dos contextos exigidos: `{report['required_contexts_source']}`",
        f"- Decisão: `{report['decision']}`",
        f"- Bloqueante: `{str(report['blocking']).lower()}`",
        f"- Workflows analisados: `{summary['workflow_count']}`",
        f"- Contextos produzíveis (check run names): `{summary['producible_context_count']}`",
        "",
        "## Classificação dos contextos exigidos",
        "",
        "| Contexto exigido | Status | Produtores | Sugestão | Decisão registrada |",
        "|---|---|---|---|---|",
    ]
    for item in report["classifications"]:
        decision = item.get("registered_decision") or {}
        decision_text = f"{decision.get('decision')} → {', '.join(decision.get('target_contexts') or []) or '-'}" if decision else "pendente" if item["decision_required"] else "-"
        lines.append(
            f"| `{item['context']}` | `{item['status']}` | {', '.join(f'`{p}`' for p in item['producers']) or '-'} "
            f"| {', '.join(f'`{s}`' for s in item['suggested_contexts']) or '-'} | {decision_text} |"
        )

    lines += ["", "## Validação da lista recomendada", "", "| Contexto recomendado | Status | Produtores |", "|---|---|---|"]
    for item in report["recommended_validation"]:
        lines.append(
            f"| `{item['context']}` | `{item['status']}` | {', '.join(f'`{p}`' for p in item['producers']) or '-'} |"
        )

    lines += [
        "",
        "## Pendências",
        "",
        f"- Stale ou renomeados: {', '.join(f'`{c}`' for c in summary['stale_contexts']) or 'nenhum'}",
        f"- Sem decisão registrada: {', '.join(f'`{c}`' for c in summary['pending_decisions']) or 'nenhuma'}",
        "",
        "## Restrições",
        "",
        "- Alteração automática de branch protection: `não permitida`.",
        "- Remoção automática de contexto: `não permitida`.",
        "- Produção tocada: `não`.",
        "",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflows-dir", type=Path, default=DEFAULT_WORKFLOW_DIR)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--protection", type=Path, default=None, help="payload de required_status_checks da API")
    parser.add_argument("--target-branch", default="main")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--strict", action="store_true", help="falha quando houver pendência sem decisão registrada")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    policy = load_json(args.policy)
    protection_payload = load_json(args.protection) if args.protection else None
    inventory = build_workflow_inventory(args.workflows_dir, target_branch=args.target_branch)
    report = build_report(
        policy=policy,
        inventory=inventory,
        protection_payload=protection_payload,
        target_branch=args.target_branch,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps({key: report[key] for key in ("decision", "blocking", "inconclusive", "summary")}, ensure_ascii=False))
    return 1 if args.strict and report["blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
