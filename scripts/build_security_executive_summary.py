#!/usr/bin/env python3
"""Security Executive Summary — consolida evidências de scanners especializados.

Report-only por padrão: não executa scanners, não acessa rede, não lê secrets e não altera runtime.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
SEVERITY_ORDER = ("critical", "high", "medium", "low", "unknown")


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def empty_counts() -> dict[str, int]:
    return {severity: 0 for severity in SEVERITY_ORDER}


def add_counts(target: dict[str, int], source: dict[str, Any]) -> None:
    for severity in SEVERITY_ORDER:
        target[severity] += int_value(source.get(severity))


def normalize_severity(value: Any) -> str:
    raw = str(value or "unknown").strip().lower()
    aliases = {
        "crit": "critical",
        "moderate": "medium",
        "info": "low",
        "informational": "low",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in SEVERITY_ORDER else "unknown"


def summarize_pip_audit(root: Path) -> dict[str, Any]:
    scanner_dir = root / "artifacts/security-scanners/pip-audit"
    counts = empty_counts()
    files = sorted(scanner_dir.glob("*.json")) if scanner_dir.exists() else []
    dependencies = 0
    for file in files:
        payload = load_json(file)
        if not isinstance(payload, dict):
            continue
        for dependency in payload.get("dependencies") or []:
            dependencies += 1
            for vulnerability in dependency.get("vulns") or []:
                severity = normalize_severity(vulnerability.get("fix_versions") and vulnerability.get("severity"))
                if severity == "unknown":
                    severity = "high"
                counts[severity] += 1
    return {
        "scanner": "pip-audit",
        "available": bool(files),
        "files": [str(file.relative_to(root)) for file in files],
        "dependencies_evaluated": dependencies,
        "findings": sum(counts.values()),
        "severity": counts,
    }


def summarize_npm_audit(root: Path) -> dict[str, Any]:
    scanner_dir = root / "artifacts/security-scanners/npm-audit"
    counts = empty_counts()
    files = sorted(scanner_dir.glob("*.json")) if scanner_dir.exists() else []
    dependencies = 0
    for file in files:
        payload = load_json(file)
        if not isinstance(payload, dict):
            continue
        metadata = payload.get("metadata") or {}
        dependencies += int_value((metadata.get("dependencies") or {}).get("total"))
        vulnerabilities = metadata.get("vulnerabilities") or {}
        for severity in SEVERITY_ORDER:
            if severity != "unknown":
                counts[severity] += int_value(vulnerabilities.get(severity))
        for item in (payload.get("vulnerabilities") or {}).values():
            severity = normalize_severity((item or {}).get("severity"))
            if not any(int_value(vulnerabilities.get(key)) for key in SEVERITY_ORDER if key != "unknown"):
                counts[severity] += 1
    return {
        "scanner": "npm-audit",
        "available": bool(files),
        "files": [str(file.relative_to(root)) for file in files],
        "dependencies_evaluated": dependencies,
        "findings": sum(counts.values()),
        "severity": counts,
    }


def summarize_gitleaks(root: Path) -> dict[str, Any]:
    candidates = list((root / "artifacts/security-scanners").glob("**/*gitleaks*.json")) if (root / "artifacts/security-scanners").exists() else []
    counts = empty_counts()
    finding_count = 0
    for file in candidates:
        payload = load_json(file)
        if isinstance(payload, list):
            finding_count += len(payload)
        elif isinstance(payload, dict):
            finding_count += int_value(payload.get("findings") or payload.get("leaks") or payload.get("count"))
    counts["critical"] = finding_count
    return {
        "scanner": "gitleaks",
        "available": bool(candidates),
        "files": [str(file.relative_to(root)) for file in candidates],
        "findings": finding_count,
        "severity": counts,
    }


def summarize_sbom(root: Path) -> dict[str, Any]:
    files = sorted((root / "artifacts/security-scanners/sbom").glob("*.json")) if (root / "artifacts/security-scanners/sbom").exists() else []
    components = 0
    for file in files:
        payload = load_json(file)
        if isinstance(payload, dict):
            components += len(payload.get("components") or [])
    counts = empty_counts()
    return {
        "scanner": "cyclonedx-sbom",
        "available": bool(files),
        "files": [str(file.relative_to(root)) for file in files],
        "components_inventory": components,
        "findings": 0,
        "severity": counts,
    }


def score_from_counts(counts: dict[str, int], missing_scanners: int) -> int:
    penalty = (
        counts["critical"] * 35
        + counts["high"] * 12
        + counts["medium"] * 4
        + counts["low"] * 1
        + missing_scanners * 5
    )
    return max(0, min(100, 100 - penalty))


def build_summary(repository: str, branch: str, root: Path = ROOT_DIR, correlation_id: str | None = None) -> dict[str, Any]:
    scanners = [
        summarize_gitleaks(root),
        summarize_pip_audit(root),
        summarize_npm_audit(root),
        summarize_sbom(root),
    ]
    totals = empty_counts()
    for scanner in scanners:
        add_counts(totals, scanner["severity"])
    missing = [scanner["scanner"] for scanner in scanners if not scanner["available"]]
    score = score_from_counts(totals, len(missing))
    state = "red" if totals["critical"] else "yellow" if totals["high"] or missing else "green"
    decision = "BLOCKED_SECURITY_CRITICAL" if totals["critical"] else "REVIEW_SECURITY_BACKLOG" if totals["high"] or missing else "SECURITY_EVIDENCE_OK"
    return {
        "schema_version": "1.0.0",
        "kind": "security_executive_summary",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "correlation_id": correlation_id or str(uuid4()),
        "repository": repository,
        "branch": branch,
        "mode": "report_only",
        "overall": {
            "state": state,
            "decision": decision,
            "score": score,
            "risk_percent": 100 - score,
            "production_blocked": totals["critical"] > 0,
            "missing_scanners": missing,
        },
        "totals": {
            "findings": sum(totals.values()),
            "severity": totals,
        },
        "scanners": {scanner["scanner"]: scanner for scanner in scanners},
        "guardrails": {
            "report_only": True,
            "merge": False,
            "deploy": False,
            "production_change": False,
            "secret_capture": False,
            "external_calls": False,
        },
        "next_safe_increment": "expor_security_executive_summary_no_ops_dashboard",
    }


def render_markdown(summary: dict[str, Any]) -> str:
    overall = summary["overall"]
    lines = [
        "# Security Executive Summary",
        "",
        f"- Decision: `{overall['decision']}`",
        f"- State: `{overall['state']}`",
        f"- Score: `{overall['score']}%`",
        f"- Risk: `{overall['risk_percent']}%`",
        f"- Production blocked: `{overall['production_blocked']}`",
        f"- Correlation ID: `{summary['correlation_id']}`",
        "",
        "## Severity totals",
        "",
        "| Severity | Count |",
        "|---|---:|",
    ]
    for severity, count in summary["totals"]["severity"].items():
        lines.append(f"| {severity} | {count} |")
    lines.extend(["", "## Scanners", "", "| Scanner | Available | Findings |", "|---|---|---:|"])
    for scanner in summary["scanners"].values():
        lines.append(f"| {scanner['scanner']} | `{scanner['available']}` | {scanner['findings']} |")
    if overall["missing_scanners"]:
        lines.extend(["", "## Missing scanners", ""])
        lines.extend(f"- `{item}`" for item in overall["missing_scanners"])
    return "\n".join(lines) + "\n"


def write_summary(summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "security-executive-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "security-executive-summary.md").write_text(render_markdown(summary), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Security Executive Summary from scanner artifacts.")
    parser.add_argument("--repo", default="local/reqsys")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--root", type=Path, default=ROOT_DIR)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/security-executive-summary"))
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when critical security findings exist.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_summary(args.repo, args.branch, args.root, args.correlation_id or None)
    write_summary(summary, args.output_dir)
    print(json.dumps({"output": str(args.output_dir / "security-executive-summary.json"), **summary["overall"]}, ensure_ascii=False))
    return 1 if args.strict and summary["overall"]["production_blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
