import copy
from pathlib import Path

import yaml

import scripts.validate_bacen_integration_surfaces as gate


def _write_config(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "governance" / "bacen" / "integration-surfaces.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _minimal_config() -> dict:
    return {
        "schema_version": "1.0.0",
        "policy": {
            "scan_roots": ["backend/app"],
            "executable_extensions": [".py"],
            "activation_requires": [
                "contract_version",
                "official_reference",
                "consumer_paths",
                "contract_tests",
            ],
        },
        "surfaces": [
            {
                "id": "pix",
                "status": "dormant",
                "contract_version": None,
                "official_reference": "https://www.bcb.gov.br/estabilidadefinanceira/pix",
                "consumer_paths": [],
                "contract_tests": [],
                "required_consumer_markers": [],
                "detection": {
                    "path_regex": r"(?i)(?:^|/)pix_client\.py$",
                    "content_regex": r"(?i)api[-_.]?pix",
                },
            }
        ],
    }


def test_current_repository_contract_is_valid():
    result = gate.validate()
    assert result["result"] == "valid"
    assert result["surfaces"]["sgs_cdi"]["status"] == "active"
    assert "backend/app/services/cdi_provider.py" in result["surfaces"]["sgs_cdi"]["detections"]
    assert result["surfaces"]["dict"]["detections"] == []
    assert result["surfaces"]["pix"]["detections"] == []
    assert result["surfaces"]["open_finance"]["detections"] == []


def test_dormant_surface_without_consumer_does_not_block(tmp_path: Path):
    config = _minimal_config()
    config_path = _write_config(tmp_path, config)

    result = gate.validate(root=tmp_path, config_path=config_path)

    assert result["result"] == "valid"
    assert result["surfaces"]["pix"]["detections"] == []


def test_new_pix_consumer_blocks_until_contract_is_declared(tmp_path: Path):
    config = _minimal_config()
    config_path = _write_config(tmp_path, config)
    client = tmp_path / "backend" / "app" / "pix_client.py"
    client.parent.mkdir(parents=True, exist_ok=True)
    client.write_text('BASE_URL = "https://api-pix.example/v2/pix"\n', encoding="utf-8")

    result = gate.validate(root=tmp_path, config_path=config_path)

    assert result["result"] == "invalid"
    assert result["surfaces"]["pix"]["detections"] == ["backend/app/pix_client.py"]
    assert any("surface=dormant" in error for error in result["errors"])


def test_surface_can_be_activated_with_explicit_contract_and_tests(tmp_path: Path):
    config = _minimal_config()
    pix = config["surfaces"][0]
    pix.update(
        {
            "status": "active",
            "contract_version": "pix-contract-v1",
            "consumer_paths": ["backend/app/pix_client.py"],
            "contract_tests": ["tests/test_pix_contract.py"],
        }
    )
    config_path = _write_config(tmp_path, config)
    client = tmp_path / "backend" / "app" / "pix_client.py"
    client.parent.mkdir(parents=True, exist_ok=True)
    client.write_text('BASE_URL = "https://api-pix.example/v2/pix"\n', encoding="utf-8")
    test_file = tmp_path / "tests" / "test_pix_contract.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_contract():\n    assert True\n", encoding="utf-8")

    result = gate.validate(root=tmp_path, config_path=config_path)

    assert result["result"] == "valid"
    assert result["surfaces"]["pix"]["detections"] == ["backend/app/pix_client.py"]


def test_same_input_is_deterministic(tmp_path: Path):
    config = _minimal_config()
    config_path = _write_config(tmp_path, copy.deepcopy(config))

    first = gate.validate(root=tmp_path, config_path=config_path)
    second = gate.validate(root=tmp_path, config_path=config_path)

    assert first == second


def test_pre_pr_readiness_executes_bacen_surface_gate():
    source = (gate.ROOT / "scripts" / "pre_pr_readiness.py").read_text(encoding="utf-8")
    assert '"bacen:integration-surfaces"' in source
    assert "scripts/validate_bacen_integration_surfaces.py" in source
