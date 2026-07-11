import json
import os
import zipfile
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_materialize_copilot_hitl.db")
os.environ.setdefault("JWT_SECRET", "reqsys-test-secret-with-minimum-safe-length")

from scripts.materialize_copilot_hitl_solution import materialize

ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT = ROOT / "artifacts/lowcode-solution-factory/copilot-hitl-agent-network/manifest.json"


def test_materializa_pac_solution_importavel(tmp_path):
    output = tmp_path / "generated"

    manifest = materialize(BLUEPRINT, output)

    assert manifest["solution_unique_name"] == "ReqSysCopilotHITL"
    assert manifest["managed"] is False
    assert manifest["requires_human_approval"] is True
    assert manifest["production_import_blocked_by_default"] is True

    package = ROOT / manifest["package"] if not Path(manifest["package"]).is_absolute() else Path(manifest["package"])
    if not package.exists():
        package = output / "ReqSysCopilotHITL_unmanaged.zip"
    assert package.exists()

    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        assert "Other/Solution.xml" in names
        assert "customizations.xml" in names
        solution_xml = archive.read("Other/Solution.xml").decode("utf-8")
        assert "ReqSysCopilotHITL" in solution_xml
        assert "<Managed>0</Managed>" in solution_xml


def test_gera_connection_references_e_environment_variables(tmp_path):
    output = tmp_path / "generated"
    materialize(BLUEPRINT, output)

    connections = json.loads((output / "connection-references.json").read_text(encoding="utf-8"))
    variables = json.loads((output / "environment-variables.json").read_text(encoding="utf-8"))
    deployment = json.loads((output / "deployment-settings.json").read_text(encoding="utf-8"))

    logical_names = {item["logical_name"] for item in connections["connection_references"]}
    assert "reqsys_sharedcommondataserviceforapps" in logical_names
    assert "reqsys_sharedapprovals" in logical_names
    assert "reqsys_sharedteams" in logical_names
    assert all(item["secret_in_source"] is False for item in connections["connection_references"])

    schema_names = {item["schema_name"] for item in variables["environment_variables"]}
    assert "reqsys_GitHubRepository" in schema_names
    assert "reqsys_RedmineBaseUrl" in schema_names
    assert "reqsys_ApprovalSlaHours" in schema_names

    assert len(deployment["ConnectionReferences"]) == len(connections["connection_references"])
    assert len(deployment["EnvironmentVariables"]) == len(variables["environment_variables"])


def test_materializacao_e_deterministica(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    manifest_first = materialize(BLUEPRINT, first)
    manifest_second = materialize(BLUEPRINT, second)

    comparable_first = {key: value for key, value in manifest_first.items() if key not in {"package", "files"}}
    comparable_second = {key: value for key, value in manifest_second.items() if key not in {"package", "files"}}
    assert comparable_first == comparable_second

    for relative_path in [
        "src/Other/Solution.xml",
        "src/customizations.xml",
        "connection-references.json",
        "environment-variables.json",
        "deployment-settings.json",
    ]:
        assert (first / relative_path).read_bytes() == (second / relative_path).read_bytes()
