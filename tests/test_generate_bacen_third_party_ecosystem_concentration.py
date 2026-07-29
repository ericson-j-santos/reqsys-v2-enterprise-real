from pathlib import Path

import yaml

from scripts.generate_bacen_third_party_ecosystem_concentration import build_report


def write_register(tmp_path: Path, providers: list[dict]) -> Path:
    path = tmp_path / "register.yaml"
    path.write_text(
        yaml.safe_dump({"providers": providers}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def provider(provider_id: str, name: str, criticality: str = "high") -> dict:
    return {"id": provider_id, "provider": name, "criticality": criticality}


def test_microsoft_aliases_are_grouped_and_flagged(tmp_path: Path) -> None:
    providers = [
        provider("T01", "Microsoft Entra ID", "critical"),
        provider("T02", "Azure Bot Service", "high"),
        provider("T03", "Microsoft Power Automate", "high"),
    ]
    report = build_report(write_register(tmp_path, providers))
    assert report["risk_signal"] == "present"
    assert report["ecosystems"]["microsoft"]["provider_count"] == 3
    assert report["concentration_signal_ecosystems"] == ["microsoft"]


def test_independent_providers_do_not_create_signal(tmp_path: Path) -> None:
    providers = [
        provider("T01", "Provider Alpha", "medium"),
        provider("T02", "Provider Beta", "medium"),
    ]
    report = build_report(write_register(tmp_path, providers))
    assert report["risk_signal"] == "none"
    assert report["automatic_blocking"] is False


def test_duplicate_provider_id_is_blocking(tmp_path: Path) -> None:
    providers = [
        provider("T01", "GitHub"),
        provider("T01", "GitHub Enterprise"),
    ]
    report = build_report(write_register(tmp_path, providers))
    assert report["automatic_blocking"] is True
    assert report["duplicate_provider_ids"] == ["T01"]


def test_missing_provider_name_is_blocking(tmp_path: Path) -> None:
    report = build_report(
        write_register(tmp_path, [{"id": "T01", "criticality": "high"}])
    )
    assert report["automatic_blocking"] is True
    assert report["structurally_invalid_provider_ids"] == ["T01"]
