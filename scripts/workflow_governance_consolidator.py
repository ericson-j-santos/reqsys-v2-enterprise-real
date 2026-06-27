#!/usr/bin/env python3
"""Workflow Governance Consolidator for ReqSys.

Mapeia workflows locais, classifica riscos de 'No jobs were run', identifica
redundâncias da runtime intelligence mesh e recomenda consolidação governada.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MESH_REDUNDANT_FILES = {
    "operational-realtime-event-mesh.yml",
    "realtime-operational-mesh.yml",
    "realtime-operational-streaming-layer.yml",
    "live-operational-control-center.yml",
}


@dataclass
class WorkflowSpec:
    file: str
    name: str
    triggers: list[str] = field(default_factory=list)
    workflow_run_parents: list[str] = field(default_factory=list)
    jobs: list[str] = field(default_factory=list)
    job_if_conditions: dict[str, list[str]] = field(default_factory=dict)
    paths_filters: list[str] = field(default_factory=list)
    has_schedule: bool = False
    has_workflow_dispatch: bool = False


@dataclass
class WorkflowAssessment:
    file: str
    name: str
    classification: str
    no_jobs_risk: str
    notification_risk: str
    cascade_risk: str
    recommendation: str
    triggers: list[str]
    workflow_run_parents: list[str]
    jobs: list[str]
    risk_patterns: list[str]


def load_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_workflow_file(path: Path) -> WorkflowSpec:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    name = path.stem
    for line in lines:
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip('"').strip("'")
            break

    triggers: list[str] = []
    workflow_run_parents: list[str] = []
    paths_filters: list[str] = []
    has_schedule = False
    has_workflow_dispatch = False

    in_on = False
    in_workflow_run = False
    in_workflows_list = False
    in_paths = False
    on_indent = 0

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        if stripped == "on:" or stripped.startswith("on:"):
            in_on = True
            on_indent = indent
            if stripped != "on:":
                trigger = stripped.split(":", 1)[1].strip()
                if trigger:
                    triggers.append(trigger)
            continue

        if in_on and indent <= on_indent and not stripped.startswith("-"):
            in_on = False
            in_workflow_run = False
            in_workflows_list = False
            in_paths = False

        if not in_on:
            continue

        if stripped.startswith("schedule:"):
            has_schedule = True
            triggers.append("schedule")
        elif stripped.startswith("workflow_dispatch"):
            has_workflow_dispatch = True
            triggers.append("workflow_dispatch")
        elif stripped.startswith("workflow_run:"):
            in_workflow_run = True
            triggers.append("workflow_run")
        elif stripped.startswith("pull_request"):
            triggers.append("pull_request")
            if "paths:" in stripped:
                in_paths = True
        elif stripped.startswith("push:"):
            triggers.append("push")
        elif stripped.startswith("paths:"):
            in_paths = True
        elif in_workflow_run and stripped.startswith("workflows:"):
            in_workflows_list = True
        elif in_workflows_list and stripped.startswith("- "):
            parent = stripped[2:].strip().strip('"').strip("'")
            workflow_run_parents.append(parent)
        elif in_paths and stripped.startswith("- "):
            paths_filters.append(stripped[2:].strip().strip('"').strip("'"))
        elif in_workflow_run and stripped.startswith("types:"):
            in_workflows_list = False
        elif in_paths and not stripped.startswith("- ") and ":" in stripped:
            in_paths = False

    jobs: list[str] = []
    job_if: dict[str, list[str]] = {}
    current_job: str | None = None
    in_jobs = False
    jobs_indent = 0

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if stripped == "jobs:":
            in_jobs = True
            jobs_indent = len(line) - len(line.lstrip())
            continue
        if not in_jobs:
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= jobs_indent and stripped and not stripped.startswith("#"):
            if stripped != "jobs:":
                in_jobs = False
            continue
        if indent == jobs_indent + 2 and stripped.endswith(":") and "if:" not in stripped:
            current_job = stripped[:-1].strip()
            jobs.append(current_job)
            job_if.setdefault(current_job, [])
            continue
        if current_job and "if:" in stripped:
            condition = stripped.split("if:", 1)[1].strip()
            job_if[current_job].append(condition)

    return WorkflowSpec(
        file=path.name,
        name=name,
        triggers=sorted(set(triggers)),
        workflow_run_parents=workflow_run_parents,
        jobs=jobs,
        job_if_conditions=job_if,
        paths_filters=paths_filters,
        has_schedule=has_schedule,
        has_workflow_dispatch=has_workflow_dispatch,
    )


def detect_risk_patterns(spec: WorkflowSpec, registry: dict[str, Any]) -> list[str]:
    patterns: list[str] = []
    mesh_noise = set(registry.get("mesh_noise_suppression", []))

    if spec.jobs and all(spec.job_if_conditions.get(job) for job in spec.jobs):
        patterns.append("all_jobs_conditional")

    if spec.workflow_run_parents and all(parent in mesh_noise for parent in spec.workflow_run_parents):
        patterns.append("workflow_run_only_mesh")

    if "pull_request" in spec.triggers and spec.paths_filters:
        patterns.append("paths_only_pr")

    if spec.has_workflow_dispatch and spec.jobs:
        all_conditional = all(spec.job_if_conditions.get(job) for job in spec.jobs)
        if all_conditional and "pull_request" in spec.triggers:
            patterns.append("dispatch_only_optional_jobs")

    if not spec.triggers and not spec.jobs:
        patterns.append("orphan")

    if spec.file in MESH_REDUNDANT_FILES and "workflow_run" in spec.triggers:
        patterns.append("mesh_cascade_source")

    return patterns


def classify_workflow(spec: WorkflowSpec, registry: dict[str, Any], patterns: list[str]) -> str:
    critical = set(registry.get("critical_workflows", []))
    informative = set(registry.get("informative_workflows", []))
    mesh_redundant = set(registry.get("mesh_redundant_workflows", []))
    mesh_central = registry.get("mesh_central_workflow", "")

    if spec.name == mesh_central:
        return "mesh_central"
    if spec.name in mesh_redundant or spec.file in MESH_REDUNDANT_FILES:
        return "mesh_redundant" if "workflow_run" in spec.triggers else "mesh_legacy_dispatch"
    if spec.name in critical:
        return "critical"
    if spec.name in informative:
        return "informative"
    if "orphan" in patterns and not spec.triggers:
        return "orphan"
    if "workflow_run_only_mesh" in patterns or "mesh_cascade_source" in patterns:
        return "redundant"
    if "paths_only_pr" in patterns or "all_jobs_conditional" in patterns:
        return "governed_skip"
    if spec.name.startswith("Product Intelligence") or "experimental" in spec.file:
        return "experimental"
    if "pull_request" in spec.triggers or "push" in spec.triggers:
        return "critical" if spec.jobs else "orphan"
    return "informative"


def assess_no_jobs_risk(spec: WorkflowSpec, patterns: list[str]) -> str:
    if "all_jobs_conditional" in patterns or "dispatch_only_optional_jobs" in patterns:
        return "high"
    if "paths_only_pr" in patterns:
        return "medium"
    if "workflow_run_only_mesh" in patterns:
        return "low"
    if not spec.jobs:
        return "high"
    return "none"


def assess_notification_risk(spec: WorkflowSpec, classification: str, registry: dict[str, Any]) -> str:
    mesh_noise = set(registry.get("mesh_noise_suppression", []))
    if spec.name in mesh_noise or classification in {"mesh_redundant", "informative", "mesh_legacy_dispatch"}:
        return "suppress"
    if classification == "critical":
        return "alert"
    if classification == "governed_skip":
        return "suppress"
    return "observe"


def assess_cascade_risk(spec: WorkflowSpec, patterns: list[str]) -> str:
    if "mesh_cascade_source" in patterns:
        return "critical"
    if spec.workflow_run_parents and len(spec.workflow_run_parents) >= 4:
        return "high"
    if "workflow_run" in spec.triggers and spec.workflow_run_parents:
        return "medium"
    return "none"


def build_recommendation(spec: WorkflowSpec, classification: str, patterns: list[str]) -> str:
    if classification == "mesh_redundant":
        return "Remover workflow_run; usar Operational Runtime Mesh Hub como entrada central."
    if classification == "mesh_legacy_dispatch":
        return "Manter apenas workflow_dispatch para auditoria retroativa."
    if "mesh_cascade_source" in patterns:
        return "Desativar gatilho workflow_run para impedir cascata e notificações falsas."
    if "all_jobs_conditional" in patterns:
        return "Adicionar job de roteamento sempre ativo ou documentar skip governado esperado."
    if "paths_only_pr" in patterns:
        return "Registrar como skip esperado fora do escopo de paths; não alertar."
    if classification == "orphan":
        return "Revisar on:/if: ou arquivar workflow órfão."
    if classification == "informative":
        return "Manter como informativo; suprimir alertas de falha no event bus."
    return "Sem ação imediata."


def assess_workflow(spec: WorkflowSpec, registry: dict[str, Any]) -> WorkflowAssessment:
    patterns = detect_risk_patterns(spec, registry)
    classification = classify_workflow(spec, registry, patterns)
    return WorkflowAssessment(
        file=spec.file,
        name=spec.name,
        classification=classification,
        no_jobs_risk=assess_no_jobs_risk(spec, patterns),
        notification_risk=assess_notification_risk(spec, classification, registry),
        cascade_risk=assess_cascade_risk(spec, patterns),
        recommendation=build_recommendation(spec, classification, patterns),
        triggers=spec.triggers,
        workflow_run_parents=spec.workflow_run_parents,
        jobs=spec.jobs,
        risk_patterns=patterns,
    )


def build_summary(assessments: list[WorkflowAssessment]) -> dict[str, Any]:
    by_class: dict[str, int] = {}
    no_jobs_high: list[str] = []
    cascade_critical: list[str] = []
    suppress_notifications: list[str] = []
    redundant: list[str] = []

    for item in assessments:
        by_class[item.classification] = by_class.get(item.classification, 0) + 1
        if item.no_jobs_risk in {"high", "medium"}:
            no_jobs_high.append(item.name)
        if item.cascade_risk in {"critical", "high"}:
            cascade_critical.append(item.name)
        if item.notification_risk == "suppress":
            suppress_notifications.append(item.name)
        if item.classification in {"mesh_redundant", "redundant"}:
            redundant.append(item.name)

    return {
        "total_workflows": len(assessments),
        "by_classification": by_class,
        "no_jobs_risk_workflows": sorted(set(no_jobs_high)),
        "cascade_risk_workflows": sorted(set(cascade_critical)),
        "notification_suppression_workflows": sorted(set(suppress_notifications)),
        "redundant_workflows": sorted(set(redundant)),
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Workflow Governance Consolidation Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Total workflows: `{summary['total_workflows']}`",
        f"- Mesh central: `{report['mesh_central']}`",
        "",
        "## Summary",
        "",
        "| Classification | Count |",
        "|---|---:|",
    ]
    for key, value in sorted(summary["by_classification"].items()):
        lines.append(f"| {key} | {value} |")

    lines.extend(["", "## No jobs were run — risco", ""])
    if summary["no_jobs_risk_workflows"]:
        for name in summary["no_jobs_risk_workflows"]:
            lines.append(f"- `{name}`")
    else:
        lines.append("- Nenhum workflow com risco elevado detectado na análise estática.")

    lines.extend(["", "## Cascata mesh — consolidar", ""])
    for name in summary["cascade_risk_workflows"]:
        lines.append(f"- `{name}`")

    lines.extend(["", "## Redundâncias", ""])
    for name in summary["redundant_workflows"]:
        lines.append(f"- `{name}` → consolidar no hub central")

    lines.extend(["", "## Recomendações prioritárias", ""])
    priority = [
        item
        for item in report["workflows"]
        if item["cascade_risk"] in {"critical", "high"} or item["classification"] in {"mesh_redundant", "redundant"}
    ]
    for item in priority[:20]:
        lines.append(f"- **{item['name']}** (`{item['classification']}`): {item['recommendation']}")

    lines.extend(
        [
            "",
            "## Separação erro real vs skip vs informativo",
            "",
            "| Tipo | Workflows |",
            "|---|---|",
            f"| Regressão real | {', '.join(f'`{n}`' for n in report.get('critical_names', [])[:8])} |",
            f"| Skip governado | {len([w for w in report['workflows'] if w['classification'] == 'governed_skip'])} workflows |",
            f"| Informativo | {len([w for w in report['workflows'] if w['classification'] == 'informative'])} workflows |",
            "",
            "## Governança",
            "",
            "- Preservar gates obrigatórios de CI.",
            "- Suprimir alertas para mesh/informativos no Unified Event Bus.",
            "- Usar `coordenador-status-evidence` como leitura preferencial.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_report(workflows_dir: Path, registry_path: Path) -> dict[str, Any]:
    registry = load_registry(registry_path)
    specs = [
        parse_workflow_file(path)
        for path in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))
    ]
    assessments = [assess_workflow(spec, registry) for spec in specs]

    critical_names = [item.name for item in assessments if item.classification == "critical"]
    summary = build_summary(assessments)

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mesh_central": registry.get("mesh_central_workflow"),
        "registry_version": registry.get("schema_version"),
        "summary": summary,
        "critical_names": critical_names,
        "workflows": [asdict(item) for item in assessments],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Workflow governance consolidator")
    parser.add_argument(
        "--workflows-dir",
        type=Path,
        default=Path(".github/workflows"),
        help="Directory containing workflow YAML files",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("config/workflow-governance-registry.json"),
        help="Governance registry JSON",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/workflow-governance"),
        help="Output directory for reports",
    )
    args = parser.parse_args(argv)

    if not args.workflows_dir.exists():
        print(f"Workflows dir not found: {args.workflows_dir}", file=sys.stderr)
        return 1
    if not args.registry.exists():
        print(f"Registry not found: {args.registry}", file=sys.stderr)
        return 1

    report = build_report(args.workflows_dir, args.registry)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    json_path = args.out_dir / "workflow-governance-consolidation.json"
    md_path = args.out_dir / "workflow-governance-consolidation.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"Workflow governance report: {json_path}")
    print(f"Summary: {report['summary']['total_workflows']} workflows assessed")
    print(f"Redundant/mesh: {len(report['summary']['redundant_workflows'])}")
    print(f"No-jobs risk: {len(report['summary']['no_jobs_risk_workflows'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
