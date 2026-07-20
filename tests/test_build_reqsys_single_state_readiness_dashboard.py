from scripts.build_reqsys_single_state_readiness_dashboard import build_dashboard


def sample_report() -> dict:
    return {
        "status": "READY",
        "readiness_percent": 100,
        "ready_consumers": 3,
        "total_consumers": 3,
        "source_contract": "reqsys-single-state",
        "source_schema_version": "1.0.0",
        "next_safe_increment": "switch governed consumers to the canonical contract",
        "consumers": {
            "governance": {"ready": True, "purpose": "merge decisions", "missing_sections": [], "empty_sections": []},
            "runtime": {"ready": True, "purpose": "runtime readiness", "missing_sections": [], "empty_sections": []},
            "analytics": {"ready": True, "purpose": "trend reporting", "missing_sections": [], "empty_sections": []},
        },
    }


def test_dashboard_renders_all_consumers_and_guardrails() -> None:
    dashboard = build_dashboard(sample_report())
    assert "Governance" in dashboard
    assert "Runtime" in dashboard
    assert "Analytics" in dashboard
    assert "100.00%" in dashboard
    assert "NÃO BLOQUEANTE" in dashboard
    assert "automatic_promotion_allowed=false" in dashboard


def test_dashboard_escapes_external_text() -> None:
    report = sample_report()
    report["next_safe_increment"] = "<script>alert(1)</script>"
    report["consumers"]["runtime"]["purpose"] = "<b>runtime</b>"
    dashboard = build_dashboard(report)
    assert "<script>" not in dashboard
    assert "&lt;script&gt;" in dashboard
    assert "<b>runtime</b>" not in dashboard
    assert "&lt;b&gt;runtime&lt;/b&gt;" in dashboard


def test_dashboard_marks_incomplete_consumer() -> None:
    report = sample_report()
    report["status"] = "EVIDENCE_INCOMPLETE"
    report["readiness_percent"] = 66.67
    report["ready_consumers"] = 2
    report["consumers"]["analytics"].update({"ready": False, "empty_sections": ["quality"]})
    dashboard = build_dashboard(report)
    assert "66.67%" in dashboard
    assert "EVIDENCE INCOMPLETE" in dashboard
    assert "quality" in dashboard
