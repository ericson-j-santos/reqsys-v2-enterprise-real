import json
import shutil
import zipfile
from pathlib import Path

import pytest

from scripts.build_teams_app_package import build_package

SOURCE = Path("infra/teams-app")
APP_ID = "11111111-2222-3333-4444-555555555555"


def _manifest_from_zip(package: Path) -> dict:
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        assert names == {"manifest.json", "color.png", "outline.png"}
        return json.loads(archive.read("manifest.json").decode("utf-8"))


def test_builder_gera_zip_instalavel_com_rsc_minimo(tmp_path: Path) -> None:
    output_dir = tmp_path / "package"
    output_zip = tmp_path / "reqsys-teams-dev.zip"

    build_package(SOURCE, output_dir, output_zip, APP_ID)
    manifest = _manifest_from_zip(output_zip)

    assert manifest["id"] == APP_ID
    assert manifest["bots"][0]["botId"] == APP_ID
    assert set(manifest["bots"][0]["scopes"]) == {"personal", "team"}
    assert manifest["webApplicationInfo"]["id"] == APP_ID
    assert manifest["authorization"]["permissions"]["resourceSpecific"] == [
        {"name": "ChannelMessage.Read.Group", "type": "Application"}
    ]
    assert "ChannelMessage.Read.All" not in json.dumps(manifest)
    assert "reqsys-api-dev.fly.dev" in manifest["validDomains"]
    assert "token.botframework.com" in manifest["validDomains"]


def test_builder_rejeita_permissao_organizacional_ampla(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(SOURCE, source)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["authorization"]["permissions"]["resourceSpecific"] = [
        {"name": "ChannelMessage.Read.All", "type": "Application"}
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="teams_manifest_rsc_not_least_privilege"):
        build_package(
            source,
            tmp_path / "package",
            tmp_path / "invalid.zip",
            APP_ID,
        )

    assert not (tmp_path / "invalid.zip").exists()
