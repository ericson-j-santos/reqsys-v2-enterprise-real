#!/usr/bin/env python3
"""Governed PR Increment Gate — bloqueia abertura de PRs quando new_front_allowed=false.

Acopla o Agent Increment Gate ao fluxo de Governed PR Automation:
  - Infere increment_type a partir de labels, corpo, titulo e branch do PR
  - Avalia contra coordenador-status (increment_gate)
  - Exit 0 = PR permitido; 1 = bloqueado

Uso em CI (Governed PR Automation, evento pull_request):
  python scripts/governed_pr_increment_gate.py \\
    --title "$PR_TITLE" --body "$PR_BODY" --labels "increment:gap_fix" \\
    --head-ref "$HEAD_REF" --live
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.agent_increment_gate import load_status_report  # noqa: E402
from scripts.coordenador_status_consolidator import evaluate_increment_intent  # noqa: E402

VALID_INCREMENT_TYPES = frozenset(
    {
        "new_front",
        "gap_fix",
        "close_duplicate",
        "hotfix",
        "consolidate",
    }
)

INCREMENT_LABEL_PREFIX = "increment:"
OPS_GAP_PATTERN = re.compile(r"OPS-GAP-\d+", re.IGNORECASE)
INCREMENT_TYPE_PATTERN = re.compile(
    r"(?:increment[-_ ]type|tipo[-_ ]de[-_ ]incremento)\s*:\s*([a-z_]+)",
    re.IGNORECASE,
)
PR_NUMBER_PATTERN = re.compile(r"(?:#|PR\s*)(\d+)", re.IGNORECASE)


def _normalize_label(label: str) -> str:
    lowered = label.strip().lower()
    if lowered.startswith(INCREMENT_LABEL_PREFIX):
        return lowered.removeprefix(INCREMENT_LABEL_PREFIX)
    return lowered


def _increment_from_labels(labels: list[str]) -> tuple[str, str, str] | None:
    for label in labels:
        normalized = _normalize_label(label)
        if normalized in VALID_INCREMENT_TYPES:
            return normalized, "", f"label:{label}"
    return None


def _increment_from_body(body: str) -> tuple[str, str, str] | None:
    match = INCREMENT_TYPE_PATTERN.search(body)
    if match:
        increment_type = match.group(1).lower()
        if increment_type in VALID_INCREMENT_TYPES:
            reference = ""
            gap_match = OPS_GAP_PATTERN.search(body)
            if gap_match:
                reference = gap_match.group(0).upper()
            pr_match = PR_NUMBER_PATTERN.search(body)
            if increment_type == "close_duplicate" and pr_match:
                reference = pr_match.group(1)
            return increment_type, reference, "body:increment-type"
    return None


def _increment_from_text_heuristics(
    title: str,
    body: str,
    head_ref: str,
) -> tuple[str, str, str] | None:
    combined = f"{title}\n{body}\n{head_ref}".lower()
    head_lower = head_ref.lower()

    if "consolidar incremento" in combined or "concluir incremento" in combined:
        return "consolidate", "", "heuristic:consolidate"

    if "close duplicate" in combined or "fechar duplicado" in combined:
        pr_match = PR_NUMBER_PATTERN.search(body) or PR_NUMBER_PATTERN.search(title)
        reference = pr_match.group(1) if pr_match else ""
        return "close_duplicate", reference, "heuristic:close_duplicate"

    if "hotfix" in head_lower or re.search(r"\bhotfix\b", combined):
        gap_match = OPS_GAP_PATTERN.search(body) or OPS_GAP_PATTERN.search(title)
        reference = gap_match.group(0).upper() if gap_match else ""
        return "hotfix", reference, "heuristic:hotfix"

    gap_match = OPS_GAP_PATTERN.search(body) or OPS_GAP_PATTERN.search(title)
    if gap_match or "gap-fix" in head_lower or "gap_fix" in head_lower:
        reference = gap_match.group(0).upper() if gap_match else ""
        return "gap_fix", reference, "heuristic:gap_fix"

    return None


def infer_increment_from_pr(
    title: str = "",
    body: str = "",
    labels: list[str] | None = None,
    head_ref: str = "",
) -> dict[str, Any]:
    """Infere increment_type e referencia a partir de metadados do PR."""
    label_list = labels or []
    for resolver in (
        lambda: _increment_from_labels(label_list),
        lambda: _increment_from_body(body),
        lambda: _increment_from_text_heuristics(title, body, head_ref),
    ):
        resolved = resolver()
        if resolved:
            increment_type, reference, source = resolved
            return {
                "increment_type": increment_type,
                "reference": reference or None,
                "inference_source": source,
            }

    return {
        "increment_type": "new_front",
        "reference": None,
        "inference_source": "default:new_front",
    }


def evaluate_pr_increment_gate(
    report: dict[str, Any],
    *,
    title: str = "",
    body: str = "",
    labels: list[str] | None = None,
    head_ref: str = "",
    pr_number: int | None = None,
    increment_type: str | None = None,
    reference: str | None = None,
) -> dict[str, Any]:
    inferred = infer_increment_from_pr(title=title, body=body, labels=labels, head_ref=head_ref)
    resolved_type = increment_type or inferred["increment_type"]
    resolved_reference = reference if reference is not None else (inferred.get("reference") or "")

    allowed, reason, detail = evaluate_increment_intent(
        report,
        resolved_type,
        resolved_reference.strip(),
    )

    gate = report.get("increment_gate") or {}
    return {
        "allowed": allowed,
        "reason": reason,
        "detail": detail,
        "increment_type": resolved_type,
        "reference": resolved_reference or None,
        "inference": inferred,
        "increment_gate": gate,
        "new_front_allowed": gate.get("new_front_allowed"),
        "blockers": gate.get("blockers") or [],
        "allowed_increment_types": gate.get("allowed_increment_types") or [],
        "pr_number": pr_number,
        "coordenador_state": report.get("state"),
        "coordenador_decision": report.get("decision"),
        "recommended_actions": report.get("recommended_actions", [])[:5],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gate de incremento acoplado a abertura de PR (Governed PR Automation)."
    )
    parser.add_argument("--title", default="", help="Titulo do PR")
    parser.add_argument("--body", default="", help="Corpo do PR")
    parser.add_argument(
        "--labels",
        default="",
        help="Labels separadas por virgula (ex.: increment:gap_fix,docs-only)",
    )
    parser.add_argument("--head-ref", default="", help="Branch head do PR")
    parser.add_argument("--pr-number", type=int, default=None, help="Numero do PR")
    parser.add_argument(
        "--increment-type",
        default="",
        choices=[*sorted(VALID_INCREMENT_TYPES), ""],
        help="Override do tipo de incremento (opcional)",
    )
    parser.add_argument("--reference", default="", help="Override de referencia OPS-GAP-* ou PR")
    parser.add_argument("--pr-json", default="", help="Metadados do PR em JSON (title, body, labels, head_ref)")
    parser.add_argument("--status-json", default="", help="coordenador-status.json existente")
    parser.add_argument("--orchestrator-json", default="")
    parser.add_argument("--health-json", default="")
    parser.add_argument("--watchdog-json", default="")
    parser.add_argument("--live", action="store_true", help="Consolidar status ao vivo via GitHub API")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--run-limit", type=int, default=50)
    parser.add_argument("--pr-limit", type=int, default=30)
    parser.add_argument("--health-limit", type=int, default=50)
    parser.add_argument("--output-dir", default="artifacts/governed-pr-increment-gate")
    parser.add_argument("--json", action="store_true", help="Imprimir somente JSON de decisao")
    return parser


def _parse_labels(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    title = args.title
    body = args.body
    labels = _parse_labels(args.labels)
    head_ref = args.head_ref
    pr_number = args.pr_number

    if args.pr_json:
        pr_payload = json.loads(Path(args.pr_json).read_text(encoding="utf-8"))
        title = pr_payload.get("title") or title
        body = pr_payload.get("body") or body
        labels = pr_payload.get("labels") or labels
        head_ref = pr_payload.get("head_ref") or head_ref
        if pr_payload.get("number") is not None:
            pr_number = int(pr_payload["number"])

    gate_args = argparse.Namespace(
        status_json=args.status_json,
        orchestrator_json=args.orchestrator_json,
        health_json=args.health_json,
        watchdog_json=args.watchdog_json,
        live=args.live,
        repo=args.repo,
        branch=args.branch,
        run_limit=args.run_limit,
        pr_limit=args.pr_limit,
        health_limit=args.health_limit,
        output_dir=str(output_dir / "sources"),
    )

    try:
        report = load_status_report(gate_args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    payload = evaluate_pr_increment_gate(
        report,
        title=title,
        body=body,
        labels=labels,
        head_ref=head_ref,
        pr_number=pr_number,
        increment_type=args.increment_type or None,
        reference=args.reference or None,
    )

    (output_dir / "governed-pr-increment-gate.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        status = "PERMITIDO" if payload["allowed"] else "BLOQUEADO"
        print(f"[{status}] {payload['reason']}")
        print(f"Tipo inferido: {payload['increment_type']} ({payload['inference']['inference_source']})")
        if payload.get("detail"):
            print(payload["detail"])
        if not payload["allowed"]:
            print("\nProximas acoes sugeridas:")
            for action in payload.get("recommended_actions", [])[:5]:
                print(
                    f"  - {action['priority']} {action['action']} "
                    f"({action.get('reference', '')}): {action['detail']}"
                )

    return 0 if payload["allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
