from pathlib import Path

import yaml

from scripts.generate_bacen_third_party_classification_risk import build_report


def write_register(tmp_path: Path, providers: list[dict]) -> Path:
    path = tmp_path / "register.yaml"
    path.write_text(
        yaml.safe_dump({"providers": providers}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def test_pending_reviews_keep_control_partial(tmp_path: Path) -> None:
    providers = [
        {
            "id": "BACEN-05-T01",
            "data_classification": "identity_claims",
            "criticality": "critical",
            "risk_review_status": "pending_formal_review",
            "dpa_status": "pending_verification",
        }
    ]
    report = build_report(write_register(tmp_path, providers))
    assert report["control_status"] == "partial"
    assert report["automatic_blocking"] is False
    assert report["summary"]["high_or_critical_provider_count"] == 1


def test_complete_reviews_allow_implemented_status(tmp_path: Path) -> None:
    providers = [
        {
            "id": "BACEN-05-T01",
            "data_classification": "identity_claims",
            "criticality": "high",
            "risk_review_status": "approved",
            "dpa_status": "signed",
        }
    ]
    report = build_report(write_register(tmp_path, providers))
    assert report["control_status"] == "implemented"
    assert report["human_action_required"] is False


def test_missing_classification_is_blocking(tmp_path: Path) -> None:
    providers = [
        {
            "id": "BACEN-05-T01",
            "criticality": "high",
            "risk_review_status": "approved",
            "dpa_status": "signed",
        }
    ]
    report = build_report(write_register(tmp_path, providers))
    assert report["automatic_blocking"] is True
    assert report["structurally_invalid_provider_ids"] == ["BACEN-05-T01"]


def test_duplicate_provider_is_blocking(tmp_path: Path) -> None:
    provider = {
        "id": "BACEN-05-T01",
        "data_classification": "operational_records",
        "criticality": "medium",
        "risk_review_status": "approved",
        "dpa_status": "signed",
    }
    report = build_report(write_register(tmp_path, [provider, provider]))
    assert report["automatic_blocking"] is True
    assert report["duplicate_provider_ids"] == ["BACEN-05-T01"]
