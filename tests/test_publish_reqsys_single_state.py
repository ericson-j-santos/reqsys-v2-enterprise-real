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


def test_build_contract_defaults_to_incomplete_evidence():
    result = build_contract({}, "source.json")

    assert result["status"] == "EVIDENCE_INCOMPLETE"
    assert result["confidence"] == "unknown"
    assert result["state"]["risks"] == []
    assert "runtime" in result["state"]["next_safe_increment"]
