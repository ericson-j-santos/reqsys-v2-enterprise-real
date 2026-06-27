from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/product_intelligence/generate_runtime_operational_evidence_ui.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_runtime_operational_evidence_ui", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def module():
    return load_module()


@pytest.fixture
def sample_graph() -> dict:
    return {
        "schema_version": "1.0.0",
        "runtime_state": "EVIDENCE_GRAPH_READY",
        "node_count": 2,
        "edge_count": 1,
        "confidence_percent": 93,
        "risk_percent": 4,
        "nodes": [
            {
                "id": "event_1",
                "label": "pull_request_state_captured",
                "source": "github_runtime_analytics",
                "state": "review_only",
                "correlation_level": "operational",
            },
            {
                "id": "event_2",
                "label": "github_actions_state_captured",
                "source": "github_runtime_analytics",
                "state": "review_only",
                "correlation_level": "ci",
            },
        ],
        "edges": [{"from": "event_1", "to": "event_2", "type": "temporal_correlation"}],
    }


def test_build_payload_consolidates_graph(module, sample_graph):
    payload = module.build_payload(sample_graph)

    assert payload["mode"] == "review_only"
    assert payload["readiness_color"] == "green"
    assert payload["node_count"] == 2
    assert payload["edge_count"] == 1
    assert payload["cards"][0]["anchor"] == "event-1"
    assert payload["edges"][0]["type"] == "temporal_correlation"


def test_classify_blocked_graph(module):
    graph = {
        "runtime_state": "EVIDENCE_GRAPH_BLOCKED",
        "confidence_percent": 60,
        "risk_percent": 35,
        "node_count": 0,
    }
    color, label = module.classify(graph)

    assert color == "red"
    assert "blocked" in label.lower()


def test_render_html_contains_navigable_nodes(module, sample_graph):
    payload = module.build_payload(sample_graph)
    html = module.render_html(payload)

    assert "Runtime Operational Evidence UI" in html
    assert 'id="event-1"' in html
    assert "Correlações temporais" in html
    assert "pull_request_state_captured" in html


def test_write_reports_generates_three_artifacts(module, sample_graph, tmp_path: Path):
    payload = module.build_payload(sample_graph)
    module.write_reports(tmp_path, payload)

    for name in (
        "runtime-operational-evidence-ui.json",
        "runtime-operational-evidence-ui.html",
        "runtime-operational-evidence-ui.md",
    ):
        assert (tmp_path / name).exists()

    saved = json.loads((tmp_path / "runtime-operational-evidence-ui.json").read_text(encoding="utf-8"))
    assert saved["name"] == "runtime-operational-evidence-ui"
