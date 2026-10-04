from pathlib import Path

import yaml

from scripts.validate_bacen_third_party_config_sources import build_report


def write_yaml(path: Path, providers: list[dict]) -> Path:
    path.write_text(
        yaml.safe_dump({"providers": providers}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def write_env(path: Path, keys: list[str]) -> Path:
    path.write_text("\n".join(f"{key}=" for key in keys) + "\n", encoding="utf-8")
    return path


def test_valid_config_sources_are_accepted(tmp_path: Path) -> None:
    register = write_yaml(
        tmp_path / "register.yaml",
        [{"id": "BACEN-05-T01", "config_source": ["CLIENT_ID", "CLIENT_SECRET"]}],
    )
    env_file = write_env(tmp_path / ".env.example", ["CLIENT_ID", "CLIENT_SECRET"])
    report = build_report(register, env_file)
    assert report["result"] == "valid"
    assert report["automatic_blocking"] is False


def test_missing_env_key_is_blocking(tmp_path: Path) -> None:
    register = write_yaml(
        tmp_path / "register.yaml",
        [{"id": "BACEN-05-T01", "config_source": ["MISSING_KEY"]}],
    )
    env_file = write_env(tmp_path / ".env.example", ["OTHER_KEY"])
    report = build_report(register, env_file)
    assert report["result"] == "invalid"
    assert report["missing_env_keys"]["BACEN-05-T01"] == ["MISSING_KEY"]


def test_inline_value_is_rejected(tmp_path: Path) -> None:
    register = write_yaml(
        tmp_path / "register.yaml",
        [{"id": "BACEN-05-T01", "config_source": ["CLIENT_SECRET=unsafe"]}],
    )
    env_file = write_env(tmp_path / ".env.example", ["CLIENT_SECRET"])
    report = build_report(register, env_file)
    assert report["result"] == "invalid"
    assert report["invalid_config_keys"]


def test_duplicate_provider_id_is_blocking(tmp_path: Path) -> None:
    providers = [
        {"id": "BACEN-05-T01", "config_source": ["CLIENT_ID"]},
        {"id": "BACEN-05-T01", "config_source": ["CLIENT_ID"]},
    ]
    report = build_report(
        write_yaml(tmp_path / "register.yaml", providers),
        write_env(tmp_path / ".env.example", ["CLIENT_ID"]),
    )
    assert report["result"] == "invalid"
    assert report["duplicate_provider_ids"] == ["BACEN-05-T01"]
