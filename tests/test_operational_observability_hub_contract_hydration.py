from __future__ import annotations

from scripts.operational_observability_hub import (
    build_correlation_chain,
    load_contract_artifacts,
)


def test_load_contract_artifacts_hydrates_canonical_routes_drift(tmp_path) -> None:
    index_path = tmp_path / "contract-artifacts-index.json"
    index_path.write_text(
        '{"version":"0.3.0","status":"governed","summary":{"runtime_contract_sync":"partial"},'
        '"traceability":{"openapi_to_ci":{"gap":"semantic_backend_route_sync_pending"}}}',
        encoding="utf-8",
    )
    validation_path = tmp_path / "openapi-contract-validation.json"
    validation_path.write_text(
        '{"status":"passed","summary":{"valid":true},"errors":[]}',
        encoding="utf-8",
    )
    routes_path = tmp_path / "openapi-routes-drift.json"
    routes_path.write_text(
        '{"status":"passed","summary":{"missing_in_openapi":0,"missing_in_backend":0}}',
        encoding="utf-8",
    )
    diff_path = tmp_path / "openapi-semantic-diff.json"
    diff_path.write_text(
        '{"status":"drift_detected","summary":{"drift_count":2,"missing_in_backend":0,"missing_in_openapi":2}}',
        encoding="utf-8",
    )

    payload = load_contract_artifacts(index_path, validation_path, routes_path, diff_path)

    assert payload["hydrated"] is True
    assert payload["summary"]["canonical_drift_count"] == 0
    assert payload["summary"]["semantic_drift_count"] == 2
    assert payload["routes_drift"]["mode"] == "canonical_strict_gate"
    assert payload["semantic_diff"]["mode"] == "advisory_only"


def test_build_correlation_chain_includes_contract_artifacts_event() -> None:
    contract_artifacts = {
        "hydrated": True,
        "summary": {
            "artifacts_available": 3,
            "canonical_drift_count": 1,
            "semantic_drift_count": 2,
            "validation_passed": True,
            "sync_gap": "semantic_backend_route_sync_pending",
        },
    }
    chain = build_correlation_chain(
        [],
        [],
        {},
        {"environments": []},
        None,
        "abc123",
        "corr-001",
        contract_artifacts,
    )

    contract_events = [item for item in chain if item["event"] == "contract_artifacts_hydrated"]
    assert len(contract_events) == 1
    assert contract_events[0]["canonical_drift_count"] == 1
    assert contract_events[0]["correlation_level"] == "contract"
