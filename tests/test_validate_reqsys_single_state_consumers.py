from scripts.validate_reqsys_single_state_consumers import validate_contract


def canonical_contract():
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-single-state",
        "consumers": {
            "governance": {
                "purpose": "merge decisions",
                "required_sections": ["decision", "governance", "risks"],
            },
            "runtime": {
                "purpose": "runtime readiness",
                "required_sections": ["runtime", "production", "risks"],
            },
            "analytics": {
                "purpose": "trend reporting",
                "required_sections": ["integration", "quality", "confidence"],
            },
        },
        "state": {
            "decision": "HOLD",
            "governance": {"merge_queue": "enabled"},
            "risks": ["human approval"],
            "runtime": {"public": "healthy"},
            "production": {"ready": False},
            "integration": {"throughput": "high"},
            "quality": {"ci_stability": "high"},
            "confidence": "high",
        },
    }


def test_all_consumers_ready_without_promoting_production():
    report = validate_contract(canonical_contract())

    assert report["status"] == "READY"
    assert report["readiness_percent"] == 100.0
    assert report["production_blocker"] is False
    assert report["automatic_promotion_allowed"] is False
    assert all(item["ready"] for item in report["consumers"].values())


def test_empty_required_section_keeps_report_incomplete():
    contract = canonical_contract()
    contract["state"]["runtime"] = {}

    report = validate_contract(contract)

    assert report["status"] == "EVIDENCE_INCOMPLETE"
    assert report["readiness_percent"] == 66.67
    assert report["consumers"]["runtime"]["empty_sections"] == ["runtime"]


def test_absent_consumer_is_reported():
    contract = canonical_contract()
    del contract["consumers"]["analytics"]

    report = validate_contract(contract)

    assert report["status"] == "EVIDENCE_INCOMPLETE"
    assert report["absent_consumers"] == ["analytics"]
    assert report["readiness_percent"] == 66.67
