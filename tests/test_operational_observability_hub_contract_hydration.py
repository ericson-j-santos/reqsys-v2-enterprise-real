from __future__ import annotations

from scripts.operational_observability_hub import (
    build_correlation_chain,
    load_contract_artifacts,
)


def test_load_contract_artifacts_hydrates_index_and_validation(tmp_path) -> None:
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
    diff_path = tmp_path / "openapi-semantic-diff.json"
    diff_path.write_text(
        '{"status":"drift_detected","summary":{"drift_count":2,"missing_in_backend":0,"missing_in_openapi":2}}',
        encoding="utf-8",
    )

    payload = load_contract_artifacts(index_path, validation_path, diff_path)

    assert payload["hydrated"] is True
    assert payload["contract_index"]["version"] == "0.3.0"
    assert payload["openapi_validation"]["status"] == "passed"
    assert payload["semantic_diff"]["drift_count"] == 2
    assert payload["summary"]["artifacts_available"] == 3


def test_build_correlation_chain_includes_contract_artifacts_event() -> None:
    contract_artifacts = {
        "hydrated": True,
        "summary": {
            "artifacts_available": 2,
            "semantic_drift_count": 1,
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
    assert contract_events[0]["semantic_drift_count"] == 1
    assert contract_events[0]["correlation_level"] == "contract"
