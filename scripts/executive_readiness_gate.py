#!/usr/bin/env python3
"""Executive Readiness Gate — decisão única para promoção de ambiente.

Report-only por padrão: não faz merge, deploy, chamadas externas nem leitura de secrets.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
STATE_SCORE = {"green": 100, "yellow": 70, "unknown": 40, "red": 0}
STATE_RANK = {"green": 0, "yellow": 1, "unknown": 1, "red": 2}

DEFAULT_INPUTS: dict[str, list[str]] = {
    "runtime_validation": [
        "artifacts/runtime-validation-consolidator/runtime-validation-snapshot.json",
        "audit/runtime-validation-consolidator/runtime-validation-snapshot.json",
    ],
    "executive_brief": [
        "docs/ops-dashboard/data/executive-brief.json",
        "artifacts/runtime-validation-consolidator/executive-brief.json",
    ],
    "public_runtime": [
        "audit/runtime/public-runtime-validation.json",
        "artifacts/runtime/public-runtime-validation.json",
    ],
    "security_executive_summary": [
        "docs/ops-dashboard/data/security-executive-summary.json",
        "artifacts/security-executive-summary/security-executive-summary.json",
        "audit/security/security-executive-summary.json",
    ],
    "security_baseline": [
        "artifacts/security-baseline-report/security-baseline-report.json",
        "audit/security/security-baseline-report.json",
    ],
    "regression_alert": [
        "artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json",
        "audit/runtime-executive-regression-alert.json",
    ],
    "post_deploy": [
        "artifacts/runtime-executive-post-deploy-state/runtime-executive-post-deploy-state.json",
        "audit/runtime-executive-post-deploy-state.json",
    ],
    "post_merge": [
        "audit/main-post-merge-validation.json",
        "audit/main-health/main-operational-post-merge-health.json",
    ],
    "pr_evidence_gate": [
        "audit/pr-evidence-gate.json",
        "artifacts/pr-evidence-gate/pr-evidence-gate.json",
    ],
}

DOMAIN_WEIGHTS = {
    "ci_cd": 15,
    "merge_queue": 10,
    "auto_merge": 8,
    "runtime_publico": 15,
    "deploy": 10,
    "smoke_checks": 12,
    "seguranca": 12,
    "regressao_temporal": 8,
    "evidencias_executivas": 10,
}

REQUIRED_FOR_PRODUCTION = (
    "ci_cd",
    "runtime_publico",
    "smoke_checks",
    "seguranca",
    "regressao_temporal",
    "evidencias_executivas",
)


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_parse_error": True, "path": str(path)}
    return payload if isinstance(payload, dict) else {"_invalid_type": type(payload).__name__}


def resolve_input(root: Path, candidates: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    for relative in candidates:
        payload = load_json(root / relative)
        if payload is not None:
            return payload, relative
    return None, None


def normalize_status(value: Any, default: str = "unknown") -> str:
    raw = str(value if value is not None else default).strip().lower()
    mapping = {
        "passed": "green",
        "pass": "green",
        "success": "green",
        "successful": "green",
        "healthy": "green",
        "ok": "green",
        "ready": "green",
        "online": "green",
        "stable": "green",
        "true": "green",
        "security_evidence_ok": "green",
        "passed_with_warnings": "yellow",
        "partial": "yellow",
        "warning": "yellow",
        "warnings": "yellow",
        "degraded": "yellow",
        "pending": "yellow",
        "review_security_backlog": "yellow",
        "false": "red",
        "failed": "red",
        "failure": "red",
        "critical": "red",
        "blocked": "red",
        "blocked_security_critical": "red",
        "missing": "red",
        "offline": "red",
        "unknown": "unknown",
        "none": "unknown",
    }
    return mapping.get(raw, raw if raw in STATE_SCORE else default)


def merge_state(*states: str) -> str:
    normalized = [normalize_status(state) for state in states if state]
    if not normalized:
        return "unknown"
    return sorted(normalized, key=lambda item: STATE_RANK.get(item, 1), reverse=True)[0]


def score_for(state: str) -> int:
    return STATE_SCORE.get(normalize_status(state), 40)


def domain(domain_id: str, label: str, state: str, score: int | None = None, available: bool = True, detail: str = "", production_blocker: bool | None = None) -> dict[str, Any]:
    normalized = normalize_status(state)
    return {
        "id": domain_id,
        "label": label,
        "state": normalized,
        "score": int(score if score is not None else score_for(normalized)),
        "available": available,
        "detail": detail,
        "production_blocker": normalized == "red" if production_blocker is None else production_blocker,
    }


def build_sources(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    sources: dict[str, Any] = {}
    meta: dict[str, Any] = {}
    for name, candidates in DEFAULT_INPUTS.items():
        payload, path = resolve_input(root, candidates)
        sources[name] = payload
        meta[name] = {"available": payload is not None, "path": path, "candidates": candidates}
    return sources, meta


def evaluate_ci_cd(runtime: dict[str, Any] | None, post_merge: dict[str, Any] | None) -> dict[str, Any]:
    if runtime:
        ready = bool(runtime.get("post_merge_ready"))
        state = "green" if ready else normalize_status(runtime.get("overall_state"), "yellow")
        blockers = runtime.get("blockers") or []
        if any("post_merge" in str(item) for item in blockers):
            state = merge_state(state, "yellow")
        return domain("ci_cd", "CI/CD", state, 100 if ready else None, True, f"post_merge_ready={ready}; blockers={len(blockers)}")
    if post_merge:
        state = normalize_status(post_merge.get("overall_status") or post_merge.get("status"))
        return domain("ci_cd", "CI/CD", state, None, True, f"post_merge status={state}")
    return domain("ci_cd", "CI/CD", "yellow", 65, False, "evidência CI/CD ausente", True)


def evaluate_runtime(runtime: dict[str, Any] | None, public_runtime: dict[str, Any] | None) -> dict[str, Any]:
    if runtime:
        ready = bool(runtime.get("public_runtime_ready"))
        return domain("runtime_publico", "Runtime público", "green" if ready else "red", 100 if ready else 0, True, f"public_runtime_ready={ready}")
    if public_runtime:
        readiness = public_runtime.get("readiness") or {}
        percent = float(readiness.get("readiness_percent") or public_runtime.get("success_percentual") or 0)
        state = "green" if percent >= 90 else "yellow" if percent >= 70 else "red"
        return domain("runtime_publico", "Runtime público", state, int(percent), True, f"readiness={percent}%")
    return domain("runtime_publico", "Runtime público", "red", 0, False, "evidência de runtime público ausente", True)


def evaluate_smoke(runtime: dict[str, Any] | None, public_runtime: dict[str, Any] | None) -> dict[str, Any]:
    smoke = ((runtime or {}).get("domains") or {}).get("public_smoke") or {}
    if smoke:
        state = normalize_status(smoke.get("state"))
        return domain("smoke_checks", "Smoke checks", state, int(smoke.get("score") or score_for(state)), bool(smoke.get("available", True)), str(smoke.get("detail") or "public_smoke"))
    if public_runtime:
        failed = int(public_runtime.get("failed") or 0)
        success = float(public_runtime.get("success_percentual") or 0)
        state = "green" if failed == 0 and success >= 100 else "yellow" if success >= 75 else "red"
        return domain("smoke_checks", "Smoke checks", state, int(success or score_for(state)), True, f"failed={failed}; success={success}%")
    return domain("smoke_checks", "Smoke checks", "red", 0, False, "smoke público ausente", True)


def evaluate_security(security_summary: dict[str, Any] | None, security: dict[str, Any] | None, brief: dict[str, Any] | None) -> dict[str, Any]:
    if security_summary:
        overall = security_summary.get("overall") or {}
        totals = security_summary.get("totals") or {}
        severity = totals.get("severity") or {}
        critical = int(severity.get("critical") or 0)
        high = int(severity.get("high") or 0)
        missing = overall.get("missing_scanners") or []
        state = "red" if bool(overall.get("production_blocked")) or critical > 0 else normalize_status(overall.get("state") or overall.get("decision"), "yellow" if missing else "green")
        score = int(overall.get("score") if overall.get("score") is not None else score_for(state))
        detail = f"source=security_executive_summary; decision={overall.get('decision', '-')}; critical={critical}; high={high}; missing_scanners={len(missing)}"
        return domain("seguranca", "Segurança", state, score, True, detail, bool(overall.get("production_blocked")) or state == "red")
    if security:
        critical = int(security.get("critical_count") or security.get("critical_findings") or 0)
        high = int(security.get("high_count") or security.get("high_findings") or 0)
        status = normalize_status(security.get("status") or security.get("overall_status"), "green")
        state = "red" if critical > 0 else "yellow" if high > 0 else status
        return domain("seguranca", "Segurança", state, None, True, f"source=security_baseline; critical={critical}; high={high}")
    semaforo = (brief or {}).get("semaforo_executivo") or {}
    state = normalize_status(semaforo.get("seguranca"), "green" if brief else "unknown")
    return domain("seguranca", "Segurança", state, None, bool(brief), f"source=executive_brief; semaforo={state}", state == "red")


def evaluate_regression(regression: dict[str, Any] | None, brief: dict[str, Any] | None) -> dict[str, Any]:
    if regression:
        blocked = bool(regression.get("production_blocked"))
        violations = int(regression.get("violations_count") or len(regression.get("violations") or []))
        status = normalize_status(regression.get("status") or regression.get("state"), "green")
        state = "red" if blocked or violations > 0 else status
        return domain("regressao_temporal", "Regressão temporal", state, None, True, f"production_blocked={blocked}; violations={violations}")
    semaforo = (brief or {}).get("semaforo_executivo") or {}
    state = normalize_status(semaforo.get("regressao_temporal"), "unknown")
    return domain("regressao_temporal", "Regressão temporal", state, None, bool(brief and state != "unknown"), f"semaforo={state}", state == "red")


def evaluate_evidence(runtime: dict[str, Any] | None, pr_gate: dict[str, Any] | None, brief: dict[str, Any] | None) -> dict[str, Any]:
    states: list[str] = []
    details: list[str] = []
    if runtime:
        gate = runtime.get("evidence_gate_consolidated") or {}
        states.append(normalize_status(gate.get("state"), "green" if gate.get("consolidated") else "yellow"))
        details.append(f"runtime_gate_consolidated={gate.get('consolidated')}")
    if pr_gate:
        gate_payload = pr_gate.get("gate") if isinstance(pr_gate.get("gate"), dict) else pr_gate
        failures = gate_payload.get("failures") or []
        states.append("red" if failures else normalize_status(gate_payload.get("status"), "green"))
        details.append(f"pr_evidence_failures={len(failures)}")
    if brief:
        states.append("green")
        details.append("executive_brief=available")
    state = merge_state(*(states or ["red"]))
    return domain("evidencias_executivas", "Evidências executivas", state, None, bool(states), " · ".join(details) or "evidências ausentes", state == "red")


def build_domains(sources: dict[str, Any]) -> dict[str, dict[str, Any]]:
    runtime = sources.get("runtime_validation")
    brief = sources.get("executive_brief")
    public_runtime = sources.get("public_runtime")
    semaforo = (brief or {}).get("semaforo_executivo") or {}
    post_deploy = sources.get("post_deploy")
    deploy_state = normalize_status((post_deploy or {}).get("status") or (post_deploy or {}).get("overall_state"), "green" if runtime and runtime.get("production_ready") else "yellow")
    return {
        "ci_cd": evaluate_ci_cd(runtime, sources.get("post_merge")),
        "merge_queue": domain("merge_queue", "Merge Queue", normalize_status(semaforo.get("merge_queue"), "green" if brief else "unknown"), available=bool(brief), detail=f"semaforo={normalize_status(semaforo.get('merge_queue'), 'green' if brief else 'unknown')}", production_blocker=False),
        "auto_merge": domain("auto_merge", "Auto-merge", normalize_status(semaforo.get("auto_merge"), "green" if brief else "unknown"), available=bool(brief), detail=f"semaforo={normalize_status(semaforo.get('auto_merge'), 'green' if brief else 'unknown')}", production_blocker=False),
        "runtime_publico": evaluate_runtime(runtime, public_runtime),
        "deploy": domain("deploy", "Deploy", deploy_state, available=bool(post_deploy or (runtime and runtime.get("production_ready"))), detail="post_deploy disponível" if post_deploy else "evidência pós-deploy ausente; gate report-only", production_blocker=deploy_state == "red"),
        "smoke_checks": evaluate_smoke(runtime, public_runtime),
        "seguranca": evaluate_security(sources.get("security_executive_summary"), sources.get("security_baseline"), brief),
        "regressao_temporal": evaluate_regression(sources.get("regression_alert"), brief),
        "evidencias_executivas": evaluate_evidence(runtime, sources.get("pr_evidence_gate"), brief),
    }


def weighted_score(domains: dict[str, dict[str, Any]]) -> int:
    total = sum(DOMAIN_WEIGHTS.values())
    return round(sum(domains[key]["score"] * DOMAIN_WEIGHTS[key] for key in DOMAIN_WEIGHTS) / total)


def collect_blockers(domains: dict[str, dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for key in REQUIRED_FOR_PRODUCTION:
        item = domains[key]
        if item["state"] == "red":
            blockers.append(f"{key}_red")
        if item["production_blocker"] and not item["available"]:
            blockers.append(f"{key}_not_evidenced")
    return sorted(set(blockers))


def build_gate(repo: str, branch: str, root: Path | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    sources, source_meta = build_sources(root or ROOT_DIR)
    domains = build_domains(sources)
    score = weighted_score(domains)
    blockers = collect_blockers(domains)
    ready = score >= 90 and not blockers and all(domains[key]["state"] in {"green", "yellow"} for key in REQUIRED_FOR_PRODUCTION)
    risk = max(0, 100 - score)
    return {
        "schema_version": "1.1.0",
        "kind": "executive_readiness_gate",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "correlation_id": correlation_id or str(uuid4()),
        "repository": repo,
        "branch": branch,
        "mode": "report_only",
        "executive_readiness": {
            "ready_for_production": ready,
            "overall_state": "green" if ready else "red" if blockers else "yellow",
            "score": score,
            "risk_percent": risk,
            "blockers": blockers,
            "decision": "READY_FOR_PRODUCTION" if ready else "BLOCKED_FOR_PRODUCTION",
        },
        "domains": domains,
        "indicators": {
            "progresso_tecnico_percent": score,
            "operacional_percent": min(100, score + 3),
            "usuario_final_percent": domains["runtime_publico"]["score"],
            "governanca_percent": min(100, score + 5),
            "producao_percent": score if ready else min(score, 89),
            "confianca_percent": max(0, 100 - risk),
            "risco_operacional_percent": risk,
            "throughput_prs_paralelos": "alto",
            "estabilidade_ci_percent": domains["ci_cd"]["score"],
            "seguranca_percent": domains["seguranca"]["score"],
        },
        "sources": source_meta,
        "guardrails": {
            "merge": False,
            "deploy": False,
            "production_change": False,
            "secret_capture": False,
            "external_calls": False,
            "report_only": True,
        },
        "next_safe_increment": "expor_executive_readiness_gate_no_runtime_executive_index_e_ops_dashboard",
    }


def render_summary(gate: dict[str, Any]) -> str:
    readiness = gate["executive_readiness"]
    lines = [
        "# Executive Readiness Gate",
        "",
        f"- Decision: `{readiness['decision']}`",
        f"- Ready for production: `{readiness['ready_for_production']}`",
        f"- Score: `{readiness['score']}%`",
        f"- Risk: `{readiness['risk_percent']}%`",
        f"- Correlation ID: `{gate['correlation_id']}`",
        "",
        "## Domains",
        "",
        "| Domain | State | Score | Production blocker | Detail |",
        "|---|---|---:|---|---|",
    ]
    for item in gate["domains"].values():
        lines.append(f"| {item['label']} | `{item['state']}` | {item['score']} | `{item['production_blocker']}` | {item['detail']} |")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- `{item}`" for item in readiness["blockers"]) if readiness["blockers"] else lines.append("- nenhum")
    lines.append("")
    return "\n".join(lines)


def write_gate(gate: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "executive-readiness-gate.json").write_text(json.dumps(gate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "summary.md").write_text(render_summary(gate), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Executive Readiness Gate from Estado Único artifacts.")
    parser.add_argument("--repo", default="local/reqsys")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--root", type=Path, default=ROOT_DIR)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/executive-readiness-gate"))
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when production is not ready.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gate = build_gate(args.repo, args.branch, args.root, args.correlation_id or None)
    write_gate(gate, args.output_dir)
    print(json.dumps({"output": str(args.output_dir / "executive-readiness-gate.json"), **gate["executive_readiness"]}, ensure_ascii=False))
    return 1 if args.strict and not gate["executive_readiness"]["ready_for_production"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
