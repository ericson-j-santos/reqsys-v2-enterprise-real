from pathlib import Path

from scripts.operational_runtime_mesh_hub import build_payload, render_markdown
from scripts.workflow_governance_consolidator import (
    MESH_REDUNDANT_FILES,
    build_report,
    classify_workflow,
    detect_risk_patterns,
    load_registry,
    parse_workflow_file,
)

REGISTRY_PATH = Path("config/workflow-governance-registry.json")
WORKFLOWS_DIR = Path(".github/workflows")


def test_parse_workflow_file_extracts_mesh_parents(tmp_path):
    workflow = tmp_path / "sample.yml"
    workflow.write_text(
        """
name: Sample Mesh
on:
  workflow_run:
    workflows:
      - "Live Operational Control Center"
    types:
      - completed
jobs:
  job-a:
    runs-on: ubuntu-latest
""".strip(),
        encoding="utf-8",
    )
    spec = parse_workflow_file(workflow)
    assert spec.name == "Sample Mesh"
    assert "workflow_run" in spec.triggers
    assert spec.workflow_run_parents == ["Live Operational Control Center"]


def test_mesh_legacy_dispatch_classification():
    registry = load_registry(REGISTRY_PATH)
    spec = parse_workflow_file(WORKFLOWS_DIR / "live-operational-control-center.yml")
    patterns = detect_risk_patterns(spec, registry)
    classification = classify_workflow(spec, registry, patterns)
    assert classification == "mesh_legacy_dispatch"
    assert "mesh_cascade_source" not in patterns


def test_build_report_includes_mesh_central():
    report = build_report(WORKFLOWS_DIR, REGISTRY_PATH)
    names = {item["name"] for item in report["workflows"]}
    assert "Operational Runtime Mesh Hub" in names
    assert "Workflow Governance Consolidator" in names
    assert report["summary"]["total_workflows"] >= 140


def test_operational_runtime_mesh_hub_suppresses_info_alerts():
    payload = build_payload("Post Merge Operational Summary", "success")
    assert payload["alert_intelligence"]["notification_suppressed"] is True
    assert payload["mesh"]["event_mesh"] == "ACTIVE"
    markdown = render_markdown(payload)
    assert "Operational Runtime Mesh Hub" in markdown


def test_mesh_redundant_files_constant_count():
    assert len(MESH_REDUNDANT_FILES) == 4
