#!/usr/bin/env python3
"""Gera relatório report-only de correlação de observabilidade operacional.

Mapeia workflows, dashboards, documentação e artifacts locais relacionados a
runtime health, delivery evidence, readiness, completion e burndown sem acessar
rede, sem mutar runtime e sem publicar segredos.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {
    "runtime_health": ("runtime", "health", "operational", "stability"),
    "delivery_evidence": ("evidence", "artifact", "audit", "report"),
    "readiness": ("readiness", "ready", "smoke", "validation"),
    "completion": ("completion", "complete", "done", "merge", "post-merge"),
    "burndown": ("burndown", "sprint", "agile", "backlog"),
}
TEXT_SUFFIXES = {".yml", ".yaml", ".json", ".md", ".html", ".py", ".mjs", ".js"}


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def git_value(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def classify(text: str) -> list[str]:
    low = text.lower()
    return [name for name, terms in CATEGORIES.items() if any(term in low for term in terms)]


def read_excerpt(path: Path, limit: int = 6000) -> str:
    if path.suffix not in TEXT_SUFFIXES:
        return path.name
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return path.name


def confidence(*values: Any) -> str:
    present = sum(1 for value in values if value not in (None, "", [], {}))
    if present >= 5:
        return "high"
    if present >= 3:
        return "medium"
    return "low"


def risk_from_status(status: Any) -> str:
    status_text = str(status or "unknown").lower()
    if status_text in {"success", "passed", "healthy", "completed", "ok", "normal"}:
        return "low"
    if status_text in {"warning", "partial", "degraded", "pending", "unknown", "missing"}:
        return "medium"
    if status_text in {"failed", "failure", "critical", "unhealthy", "high"}:
        return "high"
    return "medium"


def maturity_from_payload(payload: dict[str, Any]) -> int | None:
    for key in ("maturity_percent", "readiness_percent", "operational_score", "health_score", "score"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return max(0, min(100, round(value)))
    maturity = payload.get("maturity")
    if isinstance(maturity, dict) and isinstance(maturity.get("score"), (int, float)):
        return max(0, min(100, round(maturity["score"])))
    return None


def extract_pr(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    match = re.search(r"#(\d+)|pull/(\d+)|PR[-_ ]?(\d+)", text, re.IGNORECASE)
    return next((group for group in (match.groups() if match else []) if group), "")


def artifact_record(path: Path) -> dict[str, Any]:
    payload = load_json(path) if path.suffix == ".json" else {}
    status = payload.get("status") or payload.get("overall_status") or payload.get("conclusion") or payload.get("operational_status") or "available"
    workflow_run_id = payload.get("workflow_run_id") or payload.get("run_id") or payload.get("github_run_id")
    commit_sha = payload.get("commit_sha") or payload.get("sha") or payload.get("head_sha")
    branch = payload.get("branch") or payload.get("ref") or payload.get("source_ref")
    corr = payload.get("correlation_id") or payload.get("correlationId")
    maturity = maturity_from_payload(payload)
    return {
        "source_type": "artifact",
        "artifact_name": path.parent.name if path.parent.name != "artifacts" else path.stem,
        "path": rel(path),
        "categories": classify(rel(path) + " " + read_excerpt(path, 4000)),
        "correlation_id": corr,
        "workflow_run_id": str(workflow_run_id) if workflow_run_id else None,
        "commit_sha": commit_sha,
        "branch": branch,
        "pr": extract_pr(payload),
        "status": status,
        "maturity_percent": maturity,
        "operational_risk": payload.get("operational_risk") or risk_from_status(status),
        "confidence_level": payload.get("confidence_level") or payload.get("confidence") or confidence(corr, workflow_run_id, commit_sha, branch, maturity, status),
    }


def source_record(path: Path, source_type: str) -> dict[str, Any]:
    text = rel(path) + " " + read_excerpt(path)
    return {
        "source_type": source_type,
        "path": rel(path),
        "categories": classify(text),
        "status": "mapped",
        "operational_risk": "low",
        "confidence_level": "medium" if classify(text) else "low",
    }


def build_report() -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for base, source_type in ((ROOT / ".github" / "workflows", "workflow"), (ROOT / "docs", "dashboard_or_doc"), (ROOT / "scripts", "script")):
        if not base.exists():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file() and p.suffix in TEXT_SUFFIXES):
            rec = source_record(path, source_type)
            if rec["categories"] or "dashboard" in path.name.lower():
                files.append(rec)
    artifacts = []
    artifacts_dir = ROOT / "artifacts"
    if artifacts_dir.exists():
        for path in sorted(p for p in artifacts_dir.rglob("*") if p.is_file() and p.suffix in {".json", ".md", ".html"}):
            rec = artifact_record(path)
            if rec["categories"]:
                artifacts.append(rec)
    all_records = files + artifacts
    coverage = {cat: sum(1 for rec in all_records if cat in rec.get("categories", [])) for cat in CATEGORIES}
    maturity_values = [r["maturity_percent"] for r in artifacts if isinstance(r.get("maturity_percent"), int)]
    return {
        "schema_version": "1.0.0",
        "report_mode": "report-only",
        "generated_at": datetime.now(UTC).isoformat(),
        "repository": git_value("config", "--get", "remote.origin.url") or "local",
        "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
        "commit_sha": git_value("rev-parse", "HEAD"),
        "scope": list(CATEGORIES),
        "summary": {
            "mapped_sources": len(files),
            "mapped_artifacts": len(artifacts),
            "category_coverage": coverage,
            "maturity_percent": round(sum(maturity_values) / len(maturity_values)) if maturity_values else None,
            "operational_risk": "medium" if not artifacts else "low",
            "confidence_level": "high" if len(all_records) >= 10 else "medium" if all_records else "low",
        },
        "correlations": all_records,
        "guardrails": [
            "report-only: nenhum runtime produtivo, autenticação, deploy Fly.io ou contrato existente é alterado",
            "sem secrets: leitura local de metadados e artifacts versionáveis/gerados",
            "compatível com artifacts existentes: campos ausentes permanecem null",
        ],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = ["# Observability Correlation Report", "", f"- Modo: `{report['report_mode']}`", f"- Branch: `{report['branch']}`", f"- Commit: `{report['commit_sha']}`", f"- Fontes mapeadas: `{report['summary']['mapped_sources']}`", f"- Artifacts mapeados: `{report['summary']['mapped_artifacts']}`", f"- Risco operacional: `{report['summary']['operational_risk']}`", f"- Confiança: `{report['summary']['confidence_level']}`", "", "## Cobertura", ""]
    for cat, count in report["summary"]["category_coverage"].items():
        lines.append(f"- `{cat}`: {count}")
    lines += ["", "## Correlações", "", "| Tipo | Caminho/artifact | Categorias | Status | Run | SHA | Branch | PR | Risco | Confiança |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for item in report["correlations"]:
        name = item.get("artifact_name") or item.get("path")
        lines.append(f"| {item.get('source_type')} | `{name}` | {', '.join(item.get('categories') or [])} | {item.get('status') or ''} | {item.get('workflow_run_id') or ''} | {item.get('commit_sha') or ''} | {item.get('branch') or ''} | {item.get('pr') or ''} | {item.get('operational_risk') or ''} | {item.get('confidence_level') or ''} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate report-only observability correlation report")
    parser.add_argument("--out-dir", default="artifacts/observability-correlation-report")
    args = parser.parse_args()
    out = ROOT / args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (out / "observability-correlation-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report, out / "observability-correlation-report.md")
    print(out / "observability-correlation-report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
