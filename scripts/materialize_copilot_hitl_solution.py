from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BLUEPRINT = ROOT / "artifacts/lowcode-solution-factory/copilot-hitl-agent-network/manifest.json"
DEFAULT_OUTPUT = ROOT / "artifacts/lowcode-solution-factory/copilot-hitl-agent-network/generated"

CONNECTION_REFERENCES = {
    "reqsys_sharedcommondataserviceforapps": "shared_commondataserviceforapps",
    "reqsys_sharedteams": "shared_teams",
    "reqsys_sharedapprovals": "shared_approvals",
    "reqsys_sharedgithub": "shared_github",
    "reqsys_sharedazuredevops": "shared_visualstudioteamservices",
    "reqsys_sharedhttp": "shared_http",
}

ENVIRONMENT_VARIABLES = {
    "reqsys_GitHubRepository": "",
    "reqsys_AzureDevOpsOrganization": "",
    "reqsys_AzureDevOpsProject": "",
    "reqsys_RedmineBaseUrl": "",
    "reqsys_TeamsEscalationChannelId": "",
    "reqsys_ApprovalSlaHours": "24",
    "reqsys_MaxRetryAttempts": "5",
}


def _slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "", value)
    return normalized or "ReqSysCopilotHITL"


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _write_xml(path: Path, root: ET.Element) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _solution_xml(unique_name: str, display_name: str, version: str) -> ET.Element:
    root = ET.Element("ImportExportXml", {"version": "9.2.0.0", "SolutionPackageVersion": "9.2"})
    solution_manifest = ET.SubElement(root, "SolutionManifest")
    ET.SubElement(solution_manifest, "UniqueName").text = unique_name
    ET.SubElement(solution_manifest, "LocalizedNames").append(
        ET.Element("LocalizedName", {"description": display_name, "languagecode": "1046"})
    )
    ET.SubElement(solution_manifest, "Descriptions").append(
        ET.Element("Description", {"description": "Rede de agentes Copilot Studio com HITL persistente e governado.", "languagecode": "1046"})
    )
    ET.SubElement(solution_manifest, "Version").text = version
    ET.SubElement(solution_manifest, "Managed").text = "0"
    publisher = ET.SubElement(solution_manifest, "Publisher")
    ET.SubElement(publisher, "UniqueName").text = "reqsys"
    ET.SubElement(publisher, "LocalizedNames").append(
        ET.Element("LocalizedName", {"description": "ReqSys", "languagecode": "1046"})
    )
    ET.SubElement(publisher, "Descriptions")
    ET.SubElement(publisher, "EMailAddress")
    ET.SubElement(publisher, "SupportingWebsiteUrl")
    ET.SubElement(publisher, "CustomizationPrefix").text = "reqsys"
    ET.SubElement(publisher, "CustomizationOptionValuePrefix").text = "72700"
    ET.SubElement(solution_manifest, "RootComponents")
    ET.SubElement(solution_manifest, "MissingDependencies")
    return root


def _customizations_xml(unique_name: str) -> ET.Element:
    root = ET.Element("ImportExportXml", {"version": "9.2.0.0", "SolutionPackageVersion": "9.2"})
    for element in [
        "Entities",
        "Roles",
        "Workflows",
        "FieldSecurityProfiles",
        "Templates",
        "EntityMaps",
        "EntityRelationships",
        "OrganizationSettings",
        "optionsets",
        "CustomControls",
        "EntityDataProviders",
        "Languages",
    ]:
        ET.SubElement(root, element)
    ET.SubElement(root, "solution", {"uniquename": unique_name})
    return root


def _deployment_settings() -> dict:
    return {
        "ConnectionReferences": [
            {
                "LogicalName": logical_name,
                "ConnectionId": "",
                "ConnectorId": f"/providers/Microsoft.PowerApps/apis/{connector_id}",
            }
            for logical_name, connector_id in sorted(CONNECTION_REFERENCES.items())
        ],
        "EnvironmentVariables": [
            {"SchemaName": schema_name, "Value": value}
            for schema_name, value in sorted(ENVIRONMENT_VARIABLES.items())
        ],
    }


def _connection_reference_contract() -> dict:
    return {
        "schema_version": "1.0.0",
        "connection_references": [
            {
                "logical_name": logical_name,
                "connector_id": connector_id,
                "required": True,
                "secret_in_source": False,
            }
            for logical_name, connector_id in sorted(CONNECTION_REFERENCES.items())
        ],
    }


def _environment_variable_contract() -> dict:
    return {
        "schema_version": "1.0.0",
        "environment_variables": [
            {
                "schema_name": schema_name,
                "default_value": value,
                "required_in_production": schema_name not in {"reqsys_ApprovalSlaHours", "reqsys_MaxRetryAttempts"},
                "secret": False,
            }
            for schema_name, value in sorted(ENVIRONMENT_VARIABLES.items())
        ],
    }


def materialize(blueprint_path: Path, output_dir: Path, *, validate_with_pac: bool = False) -> dict:
    blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))
    unique_name = _slug(blueprint.get("solution_name", "ReqSysCopilotHITL"))
    display_name = blueprint.get("display_name", "ReqSys Copilot HITL")
    version = blueprint.get("version", "1.0.0.0")
    if version.count(".") == 2:
        version += ".0"

    source_dir = output_dir / "src"
    other_dir = source_dir / "Other"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    other_dir.mkdir(parents=True, exist_ok=True)

    _write_xml(other_dir / "Solution.xml", _solution_xml(unique_name, display_name, version))
    _write_xml(source_dir / "customizations.xml", _customizations_xml(unique_name))

    (output_dir / "deployment-settings.json").write_text(
        json.dumps(_deployment_settings(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "connection-references.json").write_text(
        json.dumps(_connection_reference_contract(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "environment-variables.json").write_text(
        json.dumps(_environment_variable_contract(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "blueprint.snapshot.json").write_text(
        json.dumps(blueprint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    package_path = output_dir / f"{unique_name}_unmanaged.zip"
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(source_dir.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(source_dir).as_posix())

    pac = shutil.which("pac")
    pac_validation = {"requested": validate_with_pac, "available": bool(pac), "executed": False, "success": None}
    if validate_with_pac and pac:
        unpack_dir = output_dir / "pac-validation"
        result = subprocess.run(
            [pac, "solution", "unpack", "--zipfile", str(package_path), "--folder", str(unpack_dir), "--packagetype", "Unmanaged"],
            capture_output=True,
            text=True,
            check=False,
        )
        pac_validation.update(
            {
                "executed": True,
                "success": result.returncode == 0,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            }
        )
        if result.returncode != 0:
            raise RuntimeError(f"PAC CLI rejeitou o pacote: {result.stderr}")

    manifest = {
        "schema_version": "1.0.0",
        "solution_unique_name": unique_name,
        "display_name": display_name,
        "version": version,
        "source_blueprint": _display_path(blueprint_path),
        "package": _display_path(package_path),
        "managed": False,
        "requires_human_approval": True,
        "production_import_blocked_by_default": True,
        "pac_validation": pac_validation,
        "files": [
            str(file.relative_to(output_dir))
            for file in sorted(output_dir.rglob("*"))
            if file.is_file()
        ],
    }
    (output_dir / "materialization-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Materializa a Solution Power Platform do blueprint Copilot HITL.")
    parser.add_argument("--blueprint", type=Path, default=DEFAULT_BLUEPRINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-with-pac", action="store_true")
    args = parser.parse_args()
    try:
        manifest = materialize(args.blueprint, args.output, validate_with_pac=args.validate_with_pac)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "materialized", **manifest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
