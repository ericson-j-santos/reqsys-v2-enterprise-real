#!/usr/bin/env python3
"""Build Trilha D History Index.

Gera um JSON estático consumível pelo dashboard operacional com histórico,
tendência e regressão das dimensões da Trilha D.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/trilha-d-history.json"
REFRESH_STRATEGY_ARTIFACT = "artifact_ingestion_on_trilha_d_consolidate"
REFRESH_STRATEGY_STATIC = "static_json_until_artifact_ingestion_is_enabled"
NEXT_INCREMENT_AFTER_INGESTION = "consolidate_operational_pareto_cycle"
NEXT_INCREMENT_AFTER_PARETO_DASHBOARD = "predictive_regression_gate"
NEXT_INCREMENT_AFTER_PREDICTIVE_DASHBOARD = "coverage_targeted_tests"
NEXT_INCREMENT_AFTER_COVERAGE_TARGETED = "link_governance_cards_to_latest_workflow_runs"
NEXT_INCREMENT_AFTER_GOVERNANCE_DEEP_LINKS = "dashboard_trilha_d_history_card"
NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD = "artifact_ingestion_refresh"
NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION = "continuous_trilha_d_monitoring"
NEXT_INCREMENT_AFTER_CONTINUOUS_MONITORING = "coverage_targeted_tests"
NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION_REFRESH = "merge_readiness_history"
MERGE_READINESS_HISTORY_JSON = "docs/ops-dashboard/data/merge-readiness-history.json"
CONTINUOUS_MONITORING_JSON = "docs/ops-dashboard/data/continuous-trilha-d-monitoring.json"
TRILHA_D_WORKFLOW_FILE = "trilha-d-qualidade-governanca.yml"
COVERAGE_TARGETED_MIN_SCORE = 92.0
COVERAGE_TARGETED_CRITICAL_PATH_TESTS = (
    "backend/tests/test_hub_lowcode_service_critical_paths.py",
    "backend/tests/test_wiki_publisher_critical_paths.py",
    "backend/tests/test_power_automate_provisioning_critical_paths.py",
    "backend/tests/test_recomendacoes_ia_critical_paths.py",
    "backend/tests/test_incidentes_api_critical_paths.py",
    "backend/tests/test_connection_broker_critical_paths.py",
    "backend/tests/test_relatorios_critical_paths.py",
    "backend/tests/test_figma_client_critical_paths.py",
    "backend/tests/test_async_workflows_api_critical_paths.py",
    "backend/tests/test_rag_governado_api_critical_paths.py",
    "backend/tests/test_sistema_api_critical_paths.py",
    "backend/tests/test_estatisticas_historico_critical_paths.py",
    "backend/tests/test_specs_api_critical_paths.py",
    "backend/tests/test_webhooks_api_critical_paths.py",
    "backend/tests/test_copilot_studio_provisioner_critical_paths.py",
    "backend/tests/test_agile_runtime_api_critical_paths.py",
    "backend/tests/test_pipeline_api_critical_paths.py",
    "backend/tests/test_monitoramento_snapshot_critical_paths.py",
    "backend/tests/test_azure_auth_critical_paths.py",
    "backend/tests/test_github_branch_service_critical_paths.py",
    "backend/tests/test_agile_git_sync_critical_paths.py",
    "backend/tests/test_relatorios_api_critical_paths.py",
    "backend/tests/test_rastreabilidade_api_critical_paths.py",
    "backend/tests/test_figma_github_sync_critical_paths.py",
    "backend/tests/test_codex_governado_service_critical_paths.py",
    "backend/tests/test_gemini_service_critical_paths.py",
    "backend/tests/test_github_launchpad_critical_paths.py",
)
DIMENSIONS = ("tests", "coverage", "mutation", "contract", "schema", "ci-watch")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def workflow_runs_url() -> str:
    return f"https://github.com/{REPO}/actions/workflows/{TRILHA_D_WORKFLOW_FILE}"


def resolve_history_run_url(run_id: str) -> str:
    run = str(run_id or "").strip()
    if run.isdigit():
        return f"https://github.com/{REPO}/actions/runs/{run}"
    if run.startswith("pr-"):
        return f"https://github.com/{REPO}/pull/{run.removeprefix('pr-')}"
    return workflow_runs_url()


def enrich_history_entry(entry: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(entry)
    enriched["workflow_run_url"] = resolve_history_run_url(str(entry.get("run_id") or ""))
    return enriched


def trend_for(values: list[float]) -> str:
    if len(values) < 2:
        return "stable"
    delta = round(values[-1] - values[0], 2)
    if delta >= 2:
        return "improving"
    if delta <= -2:
        return "regressing"
    return "stable"


def build_sample_history() -> list[dict[str, Any]]:
    return [
        {
            "timestamp": "2026-06-28T00:50:55Z",
            "source": "github_actions_artifact",
            "run_id": "28306826456",
            "state": "failed",
            "average_score": 88.33,
            "dimensions": {
                "tests": {"status": "passed", "score": 100.0},
                "coverage": {"status": "failed", "score": 29.0},
                "mutation": {"status": "passed", "score": 100.0},
                "contract": {"status": "passed", "score": 100.0},
                "schema": {"status": "passed", "score": 100.0},
                "ci-watch": {"status": "passed", "score": 100.0},
            },
            "notes": ["baseline_before_coverage_parser_fix"],
        },
        {
            "timestamp": "2026-06-28T01:39:18Z",
            "source": "merged_pr",
            "run_id": "pr-462",
            "state": "green",
            "average_score": 95.88,
            "dimensions": {
                "tests": {"status": "passed", "score": 100.0},
                "coverage": {"status": "passed", "score": 74.29},
                "mutation": {"status": "passed", "score": 100.0},
                "contract": {"status": "passed", "score": 100.0},
                "schema": {"status": "passed", "score": 100.0},
                "ci-watch": {"status": "passed", "score": 100.0},
            },
            "notes": ["coverage_parser_fix_merged"],
        },
        {
            "timestamp": "2026-06-28T01:43:44Z",
            "source": "merged_pr",
            "run_id": "pr-463",
            "state": "green",
            "average_score": 95.88,
            "dimensions": {
                "tests": {"status": "passed", "score": 100.0},
                "coverage": {"status": "passed", "score": 74.29},
                "mutation": {"status": "passed", "score": 100.0},
                "contract": {"status": "passed", "score": 100.0},
                "schema": {"status": "passed", "score": 100.0},
                "ci-watch": {"status": "passed", "score": 100.0},
            },
            "notes": ["coverage_parser_regression_tests_merged"],
        },
    ]


def history_state_from_report(report_state: str, average_score: float) -> str:
    if report_state == "failed":
        return "failed"
    if report_state == "warning" or average_score < 90:
        return "yellow"
    return "green"


def report_to_history_entry(report: dict[str, Any]) -> dict[str, Any]:
    dimensions: dict[str, Any] = {}
    for item in report.get("dimensions") or []:
        dimension = item.get("dimension")
        if not dimension:
            continue
        dimensions[str(dimension)] = {
            "status": item.get("status", "unknown"),
            "score": float(item.get("score") or 0.0),
        }

    average_score = round(float(report.get("average_score") or 0.0), 2)
    report_state = str(report.get("state") or "unknown")
    notes: list[str] = []
    if report.get("decision"):
        notes.append(str(report["decision"]))
    if report.get("correlation_id"):
        notes.append(f"correlation_id={report['correlation_id']}")

    return {
        "timestamp": report.get("generated_at") or utc_now(),
        "source": "github_actions_artifact",
        "run_id": str(report.get("run_id") or ""),
        "workflow_run_url": resolve_history_run_url(str(report.get("run_id") or "")),
        "state": history_state_from_report(report_state, average_score),
        "average_score": average_score,
        "dimensions": dimensions,
        "notes": notes,
    }


def load_history_from_output(output_path: str | Path) -> list[dict[str, Any]]:
    path = Path(output_path)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    history = payload.get("history")
    return list(history) if isinstance(history, list) else []


def merge_history(
    existing: list[dict[str, Any]],
    new_entry: dict[str, Any],
    *,
    max_samples: int = 50,
) -> list[dict[str, Any]]:
    run_id = str(new_entry.get("run_id") or "")
    filtered = [item for item in existing if str(item.get("run_id") or "") != run_id]
    merged = [*filtered, new_entry]
    merged.sort(key=lambda item: str(item.get("timestamp") or ""))
    return merged[-max_samples:]


def dimension_values(history: list[dict[str, Any]], dimension: str) -> list[float]:
    values: list[float] = []
    for item in history:
        dim = item.get("dimensions", {}).get(dimension, {})
        score = dim.get("score")
        if isinstance(score, int | float):
            values.append(float(score))
    return values


def build_dimension_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for dimension in DIMENSIONS:
        values = dimension_values(history, dimension)
        last_status = history[-1].get("dimensions", {}).get(dimension, {}).get("status", "unknown") if history else "unknown"
        summary[dimension] = {
            "current_status": last_status,
            "current_score": round(values[-1], 2) if values else None,
            "previous_score": round(values[-2], 2) if len(values) >= 2 else None,
            "delta_from_baseline": round(values[-1] - values[0], 2) if len(values) >= 2 else 0.0,
            "trend": trend_for(values),
            "samples": len(values),
        }
    return summary


def ops_dashboard_pareto_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    index_html = root / "docs/ops-dashboard/index.html"
    if not index_html.exists():
        return False
    text = index_html.read_text(encoding="utf-8")
    required_markers = (
        'id="trilha-d-history-card"',
        'id="operational-pareto-card"',
        "renderOperationalPareto",
        "renderTrilhaDHistory",
    )
    return all(marker in text for marker in required_markers)


def ops_dashboard_predictive_gate_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    index_html = root / "docs/ops-dashboard/index.html"
    gate_json = root / "docs/ops-dashboard/data/predictive-regression-gate.json"
    if not index_html.exists() or not gate_json.exists():
        return False
    text = index_html.read_text(encoding="utf-8")
    required_markers = (
        'id="predictive-regression-card"',
        "renderPredictiveRegressionGate",
        "predictive-regression-gate.json",
    )
    return all(marker in text for marker in required_markers)


def coverage_targeted_critical_paths_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    return all((root / relative_path).exists() for relative_path in COVERAGE_TARGETED_CRITICAL_PATH_TESTS)


def coverage_targeted_surface_ready(repo_root: Path | None = None) -> bool:
    if not coverage_targeted_critical_paths_ready(repo_root):
        return False
    root = repo_root or Path(__file__).resolve().parents[1]
    workflow = root / ".github/workflows/trilha-d-qualidade-governanca.yml"
    if not workflow.exists():
        return False
    workflow_text = workflow.read_text(encoding="utf-8")
    required_markers = (
        "Validar superfície coverage targeted",
        "test_*_critical_paths",
        f"COVERAGE_TARGETED_MIN_SCORE",
    )
    if not all(marker in workflow_text for marker in required_markers):
        return False
    history_json = root / "docs/ops-dashboard/data/trilha-d-history.json"
    if history_json.exists():
        try:
            payload = json.loads(history_json.read_text(encoding="utf-8"))
            coverage_score = (payload.get("dimension_summary") or {}).get("coverage", {}).get("current_score")
            if isinstance(coverage_score, int | float) and coverage_score < COVERAGE_TARGETED_MIN_SCORE:
                return False
        except json.JSONDecodeError:
            return False
    return True


def trilha_d_history_dashboard_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    index_html = root / "docs/ops-dashboard/index.html"
    monitoramento_view = root / "frontend/src/views/MonitoramentoOperacionalView.vue"
    history_json = root / "docs/ops-dashboard/data/trilha-d-history.json"
    if not index_html.exists() or not monitoramento_view.exists() or not history_json.exists():
        return False
    html_text = index_html.read_text(encoding="utf-8")
    view_text = monitoramento_view.read_text(encoding="utf-8")
    required_markers = ("workflow_run_url", "Ver execução")
    if not all(marker in html_text or marker in view_text for marker in required_markers):
        return False
    try:
        payload = json.loads(history_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    history = payload.get("history") or []
    return bool(history) and all(isinstance(item.get("workflow_run_url"), str) for item in history)


def governance_deep_links_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    index_html = root / "docs/ops-dashboard/index.html"
    monitoramento_view = root / "frontend/src/views/MonitoramentoOperacionalView.vue"
    governance_index = root / "docs/ops-dashboard/data/governance-evidence-index.json"
    if not index_html.exists() or not monitoramento_view.exists() or not governance_index.exists():
        return False
    html_text = index_html.read_text(encoding="utf-8")
    view_text = monitoramento_view.read_text(encoding="utf-8")
    required_markers = (
        "Última execução",
        "latest_run",
        "Ver workflow runs",
    )
    if not all(marker in html_text or marker in view_text for marker in required_markers):
        return False
    try:
        payload = json.loads(governance_index.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    evidence = payload.get("evidence") or []
    if not evidence:
        return False
    return all(
        isinstance((item.get("links") or {}).get("latest_run"), str) and item.get("dashboard_ready")
        for item in evidence
    )


def governance_workflow_deep_links_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    workflow = root / ".github/workflows/trilha-d-qualidade-governanca.yml"
    index_html = root / "docs/ops-dashboard/index.html"
    monitoramento_view = root / "frontend/src/views/MonitoramentoOperacionalView.vue"
    governance_index = root / "docs/ops-dashboard/data/governance-evidence-index.json"
    if not all(path.exists() for path in (workflow, index_html, monitoramento_view, governance_index)):
        return False
    refresh_script = root / "scripts/refresh_trilha_d_artifact_ingestion.py"
    refresh_text = refresh_script.read_text(encoding="utf-8") if refresh_script.exists() else ""
    workflow_text = workflow.read_text(encoding="utf-8")
    html_text = index_html.read_text(encoding="utf-8")
    view_text = monitoramento_view.read_text(encoding="utf-8")
    marker_corpus = "\n".join((workflow_text, html_text, view_text, refresh_text))
    required_markers = (
        "Refresh artifact ingestion Trilha D",
        "build_governance_evidence_index",
        "governance-deep-links-enabled",
        "governance_deep_links_enabled",
        "refresh_trilha_d_artifact_ingestion.py",
    )
    if not all(marker in marker_corpus for marker in required_markers):
        return False
    try:
        payload = json.loads(governance_index.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not payload.get("summary", {}).get("governance_deep_links_enabled"):
        return False
    evidence = payload.get("evidence") or []
    resolved = sum(
        1
        for item in evidence
        if isinstance((item.get("links") or {}).get("latest_run"), str) and "/actions/runs/" in item["links"]["latest_run"]
    )
    return resolved >= 2


def artifact_ingestion_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    workflow = root / ".github/workflows/trilha-d-qualidade-governanca.yml"
    index_html = root / "docs/ops-dashboard/index.html"
    monitoramento_view = root / "frontend/src/views/MonitoramentoOperacionalView.vue"
    if not workflow.exists() or not index_html.exists() or not monitoramento_view.exists():
        return False
    workflow_text = workflow.read_text(encoding="utf-8")
    html_text = index_html.read_text(encoding="utf-8")
    view_text = monitoramento_view.read_text(encoding="utf-8")
    required_markers = (
        "Refresh artifact ingestion Trilha D",
        "refresh_trilha_d_artifact_ingestion.py",
        "artifact-ingestion-enabled",
        "artifact_ingestion_enabled",
    )
    if not all(marker in workflow_text or marker in html_text or marker in view_text for marker in required_markers):
        return False
    return "refresh_trilha_d_artifact_ingestion.py" in workflow_text and "artifact-ingestion-enabled" in html_text


def artifact_ingestion_refresh_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    refresh_script = root / "scripts/refresh_trilha_d_artifact_ingestion.py"
    workflow = root / ".github/workflows/trilha-d-qualidade-governanca.yml"
    index_html = root / "docs/ops-dashboard/index.html"
    monitoramento_view = root / "frontend/src/views/MonitoramentoOperacionalView.vue"
    if not all(path.exists() for path in (refresh_script, workflow, index_html, monitoramento_view)):
        return False
    workflow_text = workflow.read_text(encoding="utf-8")
    html_text = index_html.read_text(encoding="utf-8")
    view_text = monitoramento_view.read_text(encoding="utf-8")
    required_markers = (
        "refresh_trilha_d_artifact_ingestion.py",
        "Validar superfície artifact ingestion refresh",
        "Refresh artifact ingestion Trilha D",
        "artifact-ingestion-refresh-enabled",
        "artifact_ingestion_refresh_enabled",
    )
    if not all(marker in workflow_text or marker in html_text or marker in view_text for marker in required_markers):
        return False
    return "refresh_trilha_d_artifact_ingestion.py" in workflow_text


def merge_readiness_history_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    workflow = root / ".github/workflows/merge-readiness.yml"
    index_html = root / "docs/ops-dashboard/index.html"
    history_json = root / MERGE_READINESS_HISTORY_JSON
    build_script = root / "scripts/build_merge_readiness_history.py"
    if not all(path.exists() for path in (workflow, index_html, history_json, build_script)):
        return False
    workflow_text = workflow.read_text(encoding="utf-8")
    html_text = index_html.read_text(encoding="utf-8")
    required_markers = (
        "build_merge_readiness_history.py",
        "merge-readiness-history-card",
        "merge_readiness_history_enabled",
        "--ingest-report",
    )
    if not all(marker in workflow_text or marker in html_text for marker in required_markers):
        return False
    try:
        payload = json.loads(history_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    history = payload.get("history") or []
    if not history:
        return False
    return bool(payload.get("summary", {}).get("merge_readiness_history_enabled"))


def continuous_trilha_d_monitoring_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    workflow = root / ".github/workflows/trilha-d-qualidade-governanca.yml"
    index_html = root / "docs/ops-dashboard/index.html"
    monitoramento_view = root / "frontend/src/views/MonitoramentoOperacionalView.vue"
    monitoring_json = root / CONTINUOUS_MONITORING_JSON
    build_script = root / "scripts/build_continuous_trilha_d_monitoring.py"
    if not all(path.exists() for path in (workflow, index_html, monitoramento_view, monitoring_json, build_script)):
        return False
    workflow_text = workflow.read_text(encoding="utf-8")
    html_text = index_html.read_text(encoding="utf-8")
    view_text = monitoramento_view.read_text(encoding="utf-8")
    required_markers = (
        "Validar superfície monitoramento contínuo",
        "build_continuous_trilha_d_monitoring.py",
        "continuous-trilha-d-monitoring-card",
        "continuous_monitoring_enabled",
        "continuous-trilha-d-monitoring.json",
        "refresh_trilha_d_artifact_ingestion.py",
    )
    if not all(marker in workflow_text or marker in html_text or marker in view_text for marker in required_markers):
        return False
    return "continuous-monitoring-enabled" in html_text and "continuous-trilha-d-monitoring.json" in workflow_text


def resolve_next_increment(*, artifact_ingestion: bool, repo_root: Path | None = None) -> str:
    if not ops_dashboard_pareto_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_INGESTION
    if not ops_dashboard_predictive_gate_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_PARETO_DASHBOARD
    if not coverage_targeted_critical_paths_ready(repo_root):
        return NEXT_INCREMENT_AFTER_PREDICTIVE_DASHBOARD
    if not governance_workflow_deep_links_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_COVERAGE_TARGETED
    if not trilha_d_history_dashboard_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_GOVERNANCE_DEEP_LINKS
    if not artifact_ingestion:
        return NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD
    if not artifact_ingestion_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD
    if not continuous_trilha_d_monitoring_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION
    if not coverage_targeted_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_CONTINUOUS_MONITORING
    if not merge_readiness_history_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION_REFRESH
    if not artifact_ingestion_refresh_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD
    return NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION


def build_payload(
    history: list[dict[str, Any]] | None = None,
    *,
    artifact_ingestion: bool = False,
) -> dict[str, Any]:
    samples = history if history is not None else build_sample_history()
    samples = [enrich_history_entry(item) for item in samples]
    average_values = [float(item["average_score"]) for item in samples if isinstance(item.get("average_score"), int | float)]
    current_score = round(average_values[-1], 2) if average_values else 0.0
    baseline_score = round(average_values[0], 2) if average_values else 0.0
    delta = round(current_score - baseline_score, 2)
    recent = samples[-2:] if len(samples) >= 2 else samples
    state = "green" if current_score >= 90 and recent and all(item.get("state") == "green" for item in recent) else "yellow"

    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "state": state,
        "current_score": current_score,
        "baseline_score": baseline_score,
        "delta_from_baseline": delta,
        "trend": trend_for(average_values),
        "summary": {
            "samples": len(samples),
            "green_samples": sum(1 for item in samples if item.get("state") == "green"),
            "failed_samples": sum(1 for item in samples if item.get("state") == "failed"),
            "next_increment": resolve_next_increment(artifact_ingestion=artifact_ingestion),
            "artifact_ingestion_enabled": artifact_ingestion,
            "continuous_monitoring_enabled": (
                artifact_ingestion and continuous_trilha_d_monitoring_surface_ready()
            ),
            "coverage_targeted_ready": artifact_ingestion and coverage_targeted_surface_ready(),
            "governance_deep_links_enabled": artifact_ingestion and governance_workflow_deep_links_surface_ready(),
            "artifact_ingestion_refresh_enabled": artifact_ingestion and artifact_ingestion_refresh_surface_ready(),
        },
        "links": {
            "actions": workflow_runs_url(),
            "workflow_runs": workflow_runs_url(),
            "latest_run": workflow_runs_url(),
            "source": f"https://github.com/{REPO}/blob/main/scripts/build_trilha_d_history.py",
            "dashboard_data": f"https://github.com/{REPO}/blob/main/docs/ops-dashboard/data/trilha-d-history.json",
        },
        "dimension_summary": build_dimension_summary(samples),
        "history": samples,
        "runtime_dashboard_contract": {
            "card_fields": ["state", "current_score", "trend", "delta_from_baseline", "workflow_run_url"],
            "series_fields": ["timestamp", "average_score", "state", "workflow_run_url"],
            "dimension_fields": ["current_status", "current_score", "trend", "delta_from_baseline"],
            "refresh_strategy": (
                REFRESH_STRATEGY_ARTIFACT
                if artifact_ingestion
                else (
                    "workflow_runs_deep_links_enabled"
                    if trilha_d_history_dashboard_surface_ready()
                    else REFRESH_STRATEGY_STATIC
                )
            ),
        },
    }


def write_payload(
    output_path: str,
    *,
    history: list[dict[str, Any]] | None = None,
    artifact_ingestion: bool = False,
) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(history, artifact_ingestion=artifact_ingestion)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def ingest_report_into_history(
    report_path: str,
    output_path: str,
    *,
    max_samples: int = 50,
) -> dict[str, Any]:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    existing = load_history_from_output(output_path)
    entry = report_to_history_entry(report)
    history = merge_history(existing, entry, max_samples=max_samples)
    return write_payload(output_path, history=history, artifact_ingestion=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera trilha-d-history.json para o dashboard operacional.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Imprime o payload gerado")
    parser.add_argument("--ingest-report", help="JSON consolidado da Trilha D para append no histórico")
    parser.add_argument("--max-samples", type=int, default=50, help="Máximo de amostras no histórico")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ingest_report:
        payload = ingest_report_into_history(args.ingest_report, args.output, max_samples=args.max_samples)
    else:
        payload = write_payload(args.output)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"trilha_d_history_state={payload['state']} score={payload['current_score']} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
