import pytest

from scripts.publish_reqsys_single_state import CONSUMERS, build_contract


def test_build_contract_declares_official_consumers_and_guardrails():
    source = {
        "contract": "reqsys-unified-executive-integration-index",
        "schema_version": "1.0.0",
        "decision": "EXECUTIVE_GREEN",
        "confidence": "high",
        "integration": {"throughput": "stable"},
        "quality": {"ci_stability": "high"},
        "runtime": {"public": "healthy"},
        "production": {"ready": False},
        "governance": {"merge_queue": "enabled"},
        "risks": [],
        "next_safe_increment": "collect production evidence",
    }

    result = build_contract(source, "source.json")

    assert result["contract"] == "reqsys-single-state"
    assert result["official_source"]["path"] == "source.json"
    assert result["consumers"] == CONSUMERS
    assert result["automatic_promotion_allowed"] is False
    assert result["human_approval_required"] is True
    assert result["state"]["decision"] == "EXECUTIVE_GREEN"
    assert result["state"]["credential_control_plane"]["status"] == "EVIDENCE_NOT_PROVIDED"


def test_build_contract_defaults_to_incomplete_evidence():
    result = build_contract({}, "source.json")

    assert result["status"] == "EVIDENCE_INCOMPLETE"
    assert result["confidence"] == "unknown"
    assert result["state"]["risks"] == []
    assert "runtime" in result["state"]["next_safe_increment"]


def test_build_contract_projects_sanitized_credential_health():
    credential_health = {
        "schema_version": "1.0.0",
        "contract": "reqsys-credential-control-plane-health",
        "status": "HEALTHY",
        "generated_at_epoch": 123,
        "security": {
            "stores_secret_values": False,
            "secret_values_exposed": False,
            "evidence_is_metadata_only": True,
        },
        "summary": {"bindings_total": 3, "available_bindings": 3},
        "providers_cataloged": ["fly", "github", "azure"],
        "environments": {"dev": {"status": "HEALTHY"}},
        "risks": [],
    }

    result = build_contract({}, "source.json", credential_health)

    projection = result["state"]["credential_control_plane"]
    assert projection["status"] == "HEALTHY"
    assert projection["summary"]["available_bindings"] == 3
    assert projection["security"]["secret_values_exposed"] is False


def test_build_contract_rejects_unsafe_credential_health():
    with pytest.raises(ValueError, match="secret values were exposed"):
        build_contract(
            {},
            "source.json",
            {
                "security": {
                    "stores_secret_values": False,
                    "secret_values_exposed": True,
                }
            },
        )
