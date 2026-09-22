#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_POLICY = Path("config/user-journey-acceptance-policy.json")


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON inválido em {path}: objeto esperado")
    return data


def _normalized_status(value: Any) -> str:
    return str(value or "").strip().lower()


def evaluate(evidence: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    required = list(policy.get("required_stages") or [])
    labels = dict(policy.get("stage_labels") or {})
    pass_statuses = {_normalized_status(item) for item in policy.get("pass_statuses") or []}
    rules = dict(policy.get("rules") or {})
    real_required = set(rules.get("real_evidence_required_for") or [])
    mock_forbidden = set(rules.get("mock_forbidden_for") or [])
    stages = evidence.get("stages") or {}

    if not required:
        raise ValueError("Política sem required_stages")
    if not isinstance(stages, dict):
        raise ValueError("Evidence.stages deve ser objeto")

    stage_results: dict[str, Any] = {}
    blockers: list[str] = []
    passed = 0

    for stage in required:
        raw = stages.get(stage)
        if not isinstance(raw, dict):
            raw = {}
        status = _normalized_status(raw.get("status"))
        real = raw.get("real") is True
        mocked = raw.get("mocked") is True or raw.get("simulated") is True
        evidence_ref = str(raw.get("evidence") or "").strip()
        reasons: list[str] = []

        if status not in pass_statuses:
            reasons.append("status_not_passed")
        if stage in real_required and not real:
            reasons.append("real_evidence_required")
        if stage in mock_forbidden and mocked:
            reasons.append("mocked_evidence_forbidden")
        if not evidence_ref:
            reasons.append("evidence_reference_missing")

        ok = not reasons
        if ok:
            passed += 1
        else:
            label = labels.get(stage, stage)
            blockers.append(f"{label}: {', '.join(reasons)}")

        stage_results[stage] = {
            "label": labels.get(stage, stage),
            "status": status or "missing",
            "real": real,
            "mocked": mocked,
            "evidence": evidence_ref or None,
            "passed": ok,
            "reasons": reasons,
        }

    total = len(required)
    acceptance_percent = round((passed / total) * 100.0, 2)
    accepted = passed == total

    # A regra canônica é fail-closed: 100% só é permitido quando as cinco
    # camadas estão comprovadas e a evidência operacional não usa mocks.
    if not accepted and acceptance_percent >= 100.0:
        acceptance_percent = 99.99

    return {
        "schema_version": "1.0.0",
        "policy": policy.get("policy", "real_user_journey_acceptance"),
        "feature": evidence.get("feature"),
        "environment": evidence.get("environment"),
        "accepted": accepted,
        "acceptance_status": "accepted" if accepted else "quality_blocked",
        "acceptance_percent": acceptance_percent,
        "one_hundred_percent_allowed": accepted,
        "passed_stages": passed,
        "required_stages": total,
        "stages": stage_results,
        "blocking_issues": blockers,
        "next_action": None if accepted else "Concluir a primeira etapa real pendente da jornada do usuário e reexecutar o gate.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate de aceite real da jornada do usuário")
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--policy", default=DEFAULT_POLICY, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--strict", action="store_true", help="retorna código 1 enquanto não houver aceite 100% real")
    args = parser.parse_args()

    result = evaluate(_load(args.evidence), _load(args.policy))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["accepted"] or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
