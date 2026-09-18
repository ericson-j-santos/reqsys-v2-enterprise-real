from __future__ import annotations

import json
from pathlib import Path

from scripts.build_governance_evidence_index import (
    enrich_governance_workflow_deep_links,
    enrich_links,
    governance_workflow_deep_links_ready,
    load_trilha_d_latest_run_id,
    workflow_run_url,
)
from scripts.build_trilha_d_history import governance_workflow_deep_links_surface_ready


def test_workflow_run_url_usa_run_id_quando_disponivel() -> None:
    url = workflow_run_url("trilha-d-qualidade-governanca.yml", "123456789")
    assert "/actions/runs/123456789" in url


def test_enrich_links_marca_deep_link_type() -> None:
    links = enrich_links("trilha-d-qualidade-governanca.yml", run_id="42")
    assert links["deep_link_type"] == "workflow_run"
    assert "/actions/runs/42" in links["latest_run"]


def test_enrich_governance_workflow_deep_links_resolve_trilha_d_items() -> None:
    items = enrich_governance_workflow_deep_links(
        [
            {
                "id": "continuous_trilha_d_monitoring",
                "dashboard_ready": True,
                "links": enrich_links("trilha-d-qualidade-governanca.yml"),
            },
            {
                "id": "predictive_regression",
                "dashboard_ready": True,
                "links": enrich_links("predictive-regression-guard.yml"),
            },
            {
                "id": "conflict_prediction",
                "dashboard_ready": True,
                "links": enrich_links("pr-conflict-guard.yml"),
            },
        ],
        trilha_d_run_id="99887766",
    )

    assert governance_workflow_deep_links_ready(items) is True
    assert "/actions/runs/99887766" in items[0]["links"]["latest_run"]
    assert "/actions/runs/99887766" in items[1]["links"]["latest_run"]
    assert items[2]["links"]["deep_link_type"] == "workflow_list"


def test_load_trilha_d_latest_run_id_lê_historico(tmp_path: Path) -> None:
    history = tmp_path / "trilha-d-history.json"
    history.write_text(
        json.dumps(
            {
                "history": [
                    {
                        "run_id": "555001",
                        "workflow_run_url": "https://github.com/org/repo/actions/runs/555001",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_trilha_d_latest_run_id(history) == "555001"


def test_governance_workflow_deep_links_surface_ready_detecta_superficie() -> None:
    assert governance_workflow_deep_links_surface_ready() is True
