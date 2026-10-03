#!/usr/bin/env python3
"""Report-only validator for Trilha C — UX Operacional."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "audit" / "trilha-c"
AAC = ROOT / "docs" / "architecture" / "trilha-c" / "architecture-as-code.json"

GOVERNANCE_FILES = [
    "docs/adr/ADR-038-trilha-c-ux-operacional.md",
    "docs/runbooks/trilha-c-ux-operacional.md",
    ".github/workflows/trilha-c-ux-operacional.yml",
    "docs/contracts/trilha-c-ux-operacional.schema.json",
]

UI_FILES = [
    "frontend/src/views/MonitoramentoOperacionalView.vue",
    "frontend/src/views/AnalyticsHubView.vue",
    "frontend/src/components/SemaforoChip.vue",
    "frontend/src/components/OperationalMetricCard.vue",
    "frontend/src/constants/rotasResponsivas.js",
    "frontend/src/router/index.js",
]

CAPABILITIES = ["semaforo_operacional", "drill_down", "monitoramento_operacional", "analytics_hub", "responsividade"]

REQUIRED_ROUTES = ["/monitoramento-operacional", "/analytics"]
REQUIRED_TEST_IDS = ["route-monitoramento-operacional", "route-analytics"]
REQUIRED_MARKERS = ["Trilha C"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    summary = {"governance_ok": 0, "ui_ok": 0, "ui_total": len(UI_FILES), "routes_ok": 0}

    for rel in GOVERNANCE_FILES:
        if (ROOT / rel).exists():
            summary["governance_ok"] += 1
        else:
            issues.append({"severity": "error", "type": "missing_governance", "target": rel})

    for rel in UI_FILES:
        if (ROOT / rel).exists():
            summary["ui_ok"] += 1
        else:
            issues.append({"severity": "error", "type": "missing_ui", "target": rel})

    router_text = (ROOT / "frontend/src/router/index.js").read_text(encoding="utf-8") if (ROOT / "frontend/src/router/index.js").exists() else ""
    rotas_text = (ROOT / "frontend/src/constants/rotasResponsivas.js").read_text(encoding="utf-8") if (ROOT / "frontend/src/constants/rotasResponsivas.js").exists() else ""

    for route in REQUIRED_ROUTES:
        if route in router_text and route in rotas_text:
            summary["routes_ok"] += 1
        else:
            issues.append({"severity": "error", "type": "route_missing", "target": route})

    for test_id in REQUIRED_TEST_IDS:
        if test_id not in rotas_text:
            issues.append({"severity": "warning", "type": "responsive_test_id_missing", "target": test_id})

    views_ok = 0
    for view in ("frontend/src/views/MonitoramentoOperacionalView.vue", "frontend/src/views/AnalyticsHubView.vue"):
        text = (ROOT / view).read_text(encoding="utf-8") if (ROOT / view).exists() else ""
        if any(marker in text for marker in REQUIRED_MARKERS):
            views_ok += 1
        else:
            issues.append({"severity": "warning", "type": "trilha_marker_missing", "target": view})
    summary["views_with_trilha_marker"] = views_ok

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
        "trail_id": "trilha-c",
        "trail_name": "UX Operacional",
        "mode": "report_only",
        "status": status,
        "summary": {**summary, "errors": errors, "warnings": warnings},
        "capabilities": CAPABILITIES,
        "issues": issues,
        "artifacts": {
            "architecture_as_code": "docs/architecture/trilha-c/architecture-as-code.json",
            "adr": "docs/adr/ADR-038-trilha-c-ux-operacional.md",
            "responsive_registry": "frontend/src/constants/rotasResponsivas.js",
        },
    }


def main() -> int:
    issues, summary = validate()
    report = build_report(issues, summary)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "trilha-c-ux-operacional-report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
