#!/usr/bin/env python3
"""Bloqueia regressões silenciosas nos indicadores determinísticos do ReqSys 360."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(summary: dict, rules: dict, scope: str) -> list[dict]:
    violations = []
    for metric, rule in rules.items():
        if metric not in summary:
            violations.append({
                "scope": scope,
                "metric": metric,
                "code": "BASELINE_METRIC_MISSING",
                "message": f"Métrica {scope}.{metric} não existe no relatório atual.",
            })
            continue
        value = summary[metric]
        if "max" in rule and value > rule["max"]:
            violations.append({
                "scope": scope,
                "metric": metric,
                "code": "BASELINE_MAX_EXCEEDED",
                "expected_max": rule["max"],
                "actual": value,
                "message": f"{scope}.{metric}={value} excede máximo {rule['max']}.",
            })
        if "min" in rule and value < rule["min"]:
            violations.append({
                "scope": scope,
                "metric": metric,
                "code": "BASELINE_MIN_NOT_MET",
                "expected_min": rule["min"],
                "actual": value,
                "message": f"{scope}.{metric}={value} está abaixo do mínimo {rule['min']}.",
            })
    return violations


def build_result(baseline: dict, frontend: dict, repository: dict) -> dict:
    violations = []
    violations.extend(evaluate(frontend.get("summary", {}), baseline.get("frontend", {}), "frontend"))
    violations.extend(evaluate(repository.get("summary", {}), baseline.get("repository", {}), "repository"))
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "sha": os.getenv("GITHUB_SHA"),
        "baseline_version": baseline.get("version"),
        "status": "approved" if not violations else "blocked",
        "violations": violations,
        "observed": {
            "frontend": frontend.get("summary", {}),
            "repository": repository.get("summary", {}),
        },
    }


def markdown(result: dict) -> str:
    lines = [
        "# ReqSys 360 — Guarda de regressão",
        "",
        f"- Estado: **{result['status']}**",
        f"- Baseline: **{result.get('baseline_version')}**",
        f"- SHA: `{result.get('sha') or 'local'}`",
        f"- Violações: **{len(result['violations'])}**",
        "",
    ]
    if result["violations"]:
        lines.extend(["| Código | Métrica | Mensagem |", "|---|---|---|"])
        for item in result["violations"]:
            lines.append(f"| `{item['code']}` | `{item['scope']}.{item['metric']}` | {item['message']} |")
    else:
        lines.append("Nenhuma regressão determinística acima do baseline foi detectada.")
    return "\n".join(lines) + "\n"


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    baseline = load(repo / "governance" / "reqsys-360" / "regression-baseline.json")
    frontend = load(repo / "frontend" / "artifacts" / "reqsys-360" / "reqsys-360.json")
    repository = load(repo / "artifacts" / "reqsys-360" / "repository-audit.json")
    result = build_result(baseline, frontend, repository)
    output_dir = repo / "artifacts" / "reqsys-360"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "regression.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "regression.md").write_text(markdown(result), encoding="utf-8")
    print(markdown(result))
    return 1 if result["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
