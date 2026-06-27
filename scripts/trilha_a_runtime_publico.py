#!/usr/bin/env python3
"""Report-only validator for Trilha A — Runtime Público (padrão ouro wrapper)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "audit" / "trilha-a"
AAC = ROOT / "docs" / "architecture" / "trilha-a" / "architecture-as-code.json"

GOVERNANCE_FILES = [
    "docs/adr/ADR-036-trilha-a-runtime-publico.md",
    "docs/runbooks/trilha-a-runtime-publico.md",
    ".github/workflows/trilha-a-runtime-publico.yml",
    "docs/contracts/trilha-a-runtime-publico.schema.json",
    "scripts/runtime_public_validator.py",
    "scripts/fly_boot.sh",
    "Dockerfile.fly",
    "fly.toml",
]

CAPABILITIES = ["boot_resiliente", "healthcheck_camadas", "validador_consolidado", "probe_publico"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"governance_ok": 0, "governance_total": len(GOVERNANCE_FILES), "tracks_ok": 0}

    for rel in GOVERNANCE_FILES:
        if (ROOT / rel).exists():
            summary["governance_ok"] += 1
        else:
            issues.append({"severity": "error", "type": "missing_governance", "target": rel})

    if AAC.exists():
        aac = json.loads(AAC.read_text(encoding="utf-8"))
        for cap in CAPABILITIES:
            if cap not in aac.get("capabilities", {}):
                issues.append({"severity": "error", "type": "missing_capability", "target": cap})
    else:
        issues.append({"severity": "error", "type": "missing_aac", "target": str(AAC)})

    validator = ROOT / "scripts" / "runtime_public_validator.py"
    tracks_ok = 0
    if validator.exists():
        proc = subprocess.run(
            [sys.executable, str(validator), "--artifact-root", ".", "--skip-docker"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.stdout.strip():
            try:
                payload = json.loads(proc.stdout)
                tracks = payload.get("tracks", [])
                tracks_ok = sum(1 for t in tracks if t.get("ok"))
                summary["validator_ok"] = payload.get("ok", False)
                summary["operational_status"] = payload.get("summary", {}).get("operational_status")
                summary["tracks_ok"] = tracks_ok
                summary["tracks_total"] = len(tracks)
                if proc.returncode != 0 and not payload.get("ok"):
                    issues.append({"severity": "warning", "type": "validator_blocking", "target": "runtime_public_validator"})
            except json.JSONDecodeError:
                issues.append({"severity": "warning", "type": "validator_output_invalid", "target": "runtime_public_validator"})
        elif proc.returncode != 0:
            issues.append({"severity": "warning", "type": "validator_exit_nonzero", "target": proc.stderr[-500:]})
    else:
        issues.append({"severity": "error", "type": "validator_missing", "target": str(validator)})

    return issues, summary


def build_report(issues: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    status = "failed" if errors else ("passed_with_warnings" if warnings else "passed")
    return {
        "schema_version": "1.0.0",
        "generated_at": now_iso(),
        "trail_id": "trilha-a",
        "trail_name": "Runtime Público",
        "mode": "report_only",
        "status": status,
        "summary": {**summary, "errors": errors, "warnings": warnings},
        "capabilities": CAPABILITIES,
        "issues": issues,
        "artifacts": {
            "architecture_as_code": "docs/architecture/trilha-a/architecture-as-code.json",
            "adr": "docs/adr/ADR-036-trilha-a-runtime-publico.md",
            "validator": "scripts/runtime_public_validator.py",
        },
    }


def main() -> int:
    issues, summary = validate()
    report = build_report(issues, summary)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "trilha-a-runtime-publico-report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
