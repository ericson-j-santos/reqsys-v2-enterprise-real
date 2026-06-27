#!/usr/bin/env python3
"""Report-only validator for Trilha B — Observabilidade Enterprise."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "audit" / "trilha-b"
AAC = ROOT / "docs" / "architecture" / "trilha-b" / "architecture-as-code.json"

GOVERNANCE_FILES = [
    "docs/adr/ADR-037-trilha-b-observabilidade-enterprise.md",
    "docs/runbooks/trilha-b-observabilidade-enterprise.md",
    ".github/workflows/trilha-b-observabilidade-enterprise.yml",
    "docs/contracts/trilha-b-observabilidade-enterprise.schema.json",
]

CODE_FILES = [
    "backend/app/middleware/observability.py",
    "backend/app/core/feature_metrics.py",
    "backend/app/core/correlation.py",
    "backend/app/core/otel.py",
    "backend/tests/test_observability_enterprise.py",
]

CAPABILITIES = ["correlation_id", "feature_metrics", "operational_telemetry", "distributed_tracing"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_contains(path: Path, needle: str) -> bool:
    if not path.exists():
        return False
    return needle in path.read_text(encoding="utf-8")


def validate() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    summary = {"governance_ok": 0, "code_ok": 0, "code_total": len(CODE_FILES)}

    for rel in GOVERNANCE_FILES:
        if (ROOT / rel).exists():
            summary["governance_ok"] += 1
        else:
            issues.append({"severity": "error", "type": "missing_governance", "target": rel})

    for rel in CODE_FILES:
        if (ROOT / rel).exists():
            summary["code_ok"] += 1
        else:
            issues.append({"severity": "error", "type": "missing_code", "target": rel})

    if not file_contains(ROOT / "backend/app/middleware/observability.py", "X-Correlation-Id"):
        issues.append({"severity": "warning", "type": "correlation_header_missing", "target": "middleware"})

    if not file_contains(ROOT / "backend/app/api/monitoramento_operacional.py", "reqsys_http_requests_total"):
        issues.append({"severity": "warning", "type": "metrics_counter_missing", "target": "monitoramento_operacional"})

    if AAC.exists():
        aac = json.loads(AAC.read_text(encoding="utf-8"))
        for cap in CAPABILITIES:
            if cap not in aac.get("capabilities", {}):
                issues.append({"severity": "error", "type": "missing_capability", "target": cap})
    else:
        issues.append({"severity": "error", "type": "missing_aac", "target": str(AAC)})

    return issues, summary


def build_report(issues: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    status = "failed" if errors else ("passed_with_warnings" if warnings else "passed")
    return {
        "schema_version": "1.0.0",
        "generated_at": now_iso(),
        "trail_id": "trilha-b",
        "trail_name": "Observabilidade Enterprise",
        "mode": "report_only",
        "status": status,
        "summary": {**summary, "errors": errors, "warnings": warnings},
        "capabilities": CAPABILITIES,
        "issues": issues,
        "artifacts": {
            "architecture_as_code": "docs/architecture/trilha-b/architecture-as-code.json",
            "adr": "docs/adr/ADR-037-trilha-b-observabilidade-enterprise.md",
            "tests": "backend/tests/test_observability_enterprise.py",
        },
    }


def main() -> int:
    issues, summary = validate()
    report = build_report(issues, summary)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "trilha-b-observabilidade-enterprise-report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
