#!/usr/bin/env python3
"""E2E governado do ReqSys Report Factory no Microsoft Fabric DEV."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load_report_factory() -> Any:
    module_path = ROOT / "tools" / "geradores" / "report_factory.py"
    spec = importlib.util.spec_from_file_location("reqsys_report_factory", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("report_factory_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report_factory = _load_report_factory()

FABRIC_BASE = "https://api.fabric.microsoft.com/v1"
WORKSPACE_NAME = "ReqSys - Observabilidade"
ENVIRONMENT = "development"


class E2EError(RuntimeError):
    """Erro sanitizado e seguro para evidência/log."""


def _safe_fabric_error_codes(raw: str) -> list[str]:
    """Extrai somente códigos estruturados do Fabric, inclusive aninhados."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ["unknown"]

    codes: list[str] = []

    def visit(value: Any) -> None:
        if len(codes) >= 6:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"errorCode", "code"} and isinstance(item, str):
                    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", item.strip())
                    normalized = normalized.strip("_.-")[:80]
                    if normalized and normalized not in codes:
                        codes.append(normalized)
                elif isinstance(item, (dict, list)):
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return codes or ["unknown"]


def _safe_fabric_error_code(raw: str) -> str:
    """Compatibilidade: retorna o primeiro código estruturado sanitizado."""
    return _safe_fabric_error_codes(raw)[0]


_SAFE_RDL_DIAGNOSTIC_TERMS = frozenset({
    "AutoRefresh",
    "Body",
    "CellDefinition",
    "CellDefinitions",
    "CommandText",
    "ConnectionProperties",
    "DataField",
    "DataSet",
    "DataSetName",
    "DataSets",
    "DataSource",
    "DataSourceName",
    "DataSources",
    "DefaultFontFamily",
    "Field",
    "Fields",
    "GridLayoutDefinition",
    "Group",
    "IntegratedSecurity",
    "Page",
    "Paragraph",
    "Paragraphs",
    "Query",
    "QueryParameter",
    "QueryParameters",
    "Report",
    "ReportItems",
    "ReportParameter",
    "ReportParameters",
    "ReportParametersLayout",
    "ReportSection",
    "ReportSections",
    "ReportUnitType",
    "Style",
    "Tablix",
    "TablixBody",
    "TablixCell",
    "TablixCells",
    "TablixColumn",
    "TablixColumnHierarchy",
    "TablixColumns",
    "TablixMember",
    "TablixMembers",
    "TablixRow",
    "TablixRowHierarchy",
    "TablixRows",
    "TextRun",
    "TextRuns",
    "Textbox",
    "Value",
    "Width",
})
_SAFE_RDL_LOCATION_RE = re.compile(
    r"(?i)\b(line|column|position)\s*(?:number\s*)?[:=#]?\s*(\d{1,6})\b"
)


def _safe_fabric_rdl_diagnostics(raw: str) -> list[str]:
    """Extrai somente tokens RDL allowlisted e coordenadas de mensagens estruturadas."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []

    diagnostic_texts: list[str] = []

    def visit(value: Any) -> None:
        if len(diagnostic_texts) >= 12:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "message" and isinstance(item, str):
                    diagnostic_texts.append(item[:1200])
                elif key == "parameters" and isinstance(item, list):
                    for parameter in item[:8]:
                        if not isinstance(parameter, dict):
                            continue
                        name = str(parameter.get("name") or "")[:120]
                        raw_value = str(parameter.get("value") or "")[:240]
                        diagnostic_texts.append(f"{name} {raw_value}")
                elif isinstance(item, (dict, list)):
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)

    findings: list[str] = []
    for diagnostic_text in diagnostic_texts:
        for term in sorted(_SAFE_RDL_DIAGNOSTIC_TERMS, key=lambda item: (-len(item), item)):
            if re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])",
                diagnostic_text,
            ):
                finding = f"rdl_{term}"
                if finding not in findings:
                    findings.append(finding)
        for label, number in _SAFE_RDL_LOCATION_RE.findall(diagnostic_text):
            finding = f"{label.casefold()}_{number}"
            if finding not in findings:
                findings.append(finding)
        if len(findings) >= 6:
            break

    return findings[:6]


def _run(args: list[str], timeout: int = 60) -> str:
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
    )
    if proc.returncode != 0:
        raise E2EError(f"command_failed:{Path(args[0]).name}:{proc.returncode}")
    return (proc.stdout or "").strip()


def _find_az() -> str:
    az = shutil.which("az")
    if not az:
        raise E2EError("azure_cli_missing")
    return az


def _fabric_token() -> str:
    token = _run(
        [
            _find_az(),
            "account",
            "get-access-token",
            "--resource",
            "https://api.fabric.microsoft.com",
            "--query",
            "accessToken",
            "-o",
            "tsv",
            "--only-show-errors",
        ]
    )
    if not token:
        raise E2EError("fabric_token_missing")
    return token


def _request_json(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
            body = json.loads(raw) if raw else {}
            return response.status, dict(response.headers.items()), body if isinstance(body, dict) else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        safe_codes = _safe_fabric_error_codes(raw)
        safe_diagnostics = _safe_fabric_rdl_diagnostics(raw)
        safe_suffix = ":".join((safe_codes + safe_diagnostics)[:8])
        raise E2EError(f"fabric_http_{exc.code}:{safe_suffix}") from None


def _paged_values(url: str, token: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current = url
    while current:
        if not current.startswith(FABRIC_BASE):
            raise E2EError("continuation_uri_outside_fabric")
        status, _, body = _request_json("GET", current, token)
        if status != 200:
            raise E2EError(f"list_http_{status}")
        rows.extend(item for item in body.get("value", []) if isinstance(item, dict))
        current = str(body.get("continuationUri") or "").strip()
    return rows


def _exact_by_display_name(
    rows: list[dict[str, Any]], name: str, label: str
) -> list[dict[str, Any]]:
    matches = [row for row in rows if str(row.get("displayName") or "") == name]
    if len(matches) > 1:
        raise E2EError(f"{label}_ambiguous:{len(matches)}")
    return matches


def _operation_id(headers: dict[str, str], location: str) -> str:
    lowered = {str(k).casefold(): str(v) for k, v in headers.items()}
    operation_id = lowered.get("x-ms-operation-id", "").strip()
    if operation_id:
        return operation_id
    tail = location.rstrip("/").rsplit("/", 1)[-1].strip()
    if not tail or "?" in tail:
        raise E2EError("operation_id_missing")
    return tail


def _wait_operation(
    headers: dict[str, str],
    token: str,
    *,
    require_result: bool,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    lowered = {str(k).casefold(): str(v) for k, v in headers.items()}
    location = lowered.get("location", "").strip()
    if not location.startswith(FABRIC_BASE):
        raise E2EError("operation_location_missing_or_invalid")
    operation_id = _operation_id(headers, location)
    deadline = time.monotonic() + timeout_seconds
    retry_after = 2

    while time.monotonic() < deadline:
        status, poll_headers, body = _request_json("GET", location, token)
        if status != 200:
            raise E2EError(f"operation_poll_http_{status}")
        state = str(body.get("status") or "").casefold()
        if state in {"failed", "cancelled", "canceled"}:
            raise E2EError(f"operation_terminal_{state}")
        if state in {"succeeded", "completed"}:
            if not require_result:
                return body
            poll_lower = {str(k).casefold(): str(v) for k, v in poll_headers.items()}
            result_url = poll_lower.get("location", "").strip()
            if not result_url or result_url == location:
                result_url = f"{FABRIC_BASE}/operations/{operation_id}/result"
            if not result_url.startswith(FABRIC_BASE):
                raise E2EError("operation_result_location_invalid")
            result_status, _, result = _request_json("GET", result_url, token)
            if result_status != 200:
                raise E2EError(f"operation_result_http_{result_status}")
            return result

        poll_lower = {str(k).casefold(): str(v) for k, v in poll_headers.items()}
        try:
            retry_after = int(poll_lower.get("retry-after", str(retry_after)) or retry_after)
        except ValueError:
            retry_after = 2
        time.sleep(max(1, min(retry_after, 10)))

    raise E2EError("operation_timeout")


def _invoke(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
    *,
    success: set[int],
    require_lro_result: bool = False,
) -> dict[str, Any]:
    status, headers, body = _request_json(method, url, token, payload)
    if status in success:
        return body
    if status == 202:
        return _wait_operation(headers, token, require_result=require_lro_result)
    raise E2EError(f"unexpected_http_{status}")


def _extract_rdl(definition_response: dict[str, Any], report_name: str) -> str:
    definition = definition_response.get("definition")
    if not isinstance(definition, dict):
        definition = definition_response
    parts = definition.get("parts")
    if not isinstance(parts, list):
        raise E2EError("definition_parts_missing")
    expected_path = f"{report_name}.rdl"
    matches = [
        item
        for item in parts
        if isinstance(item, dict)
        and str(item.get("path") or "") == expected_path
        and str(item.get("payloadType") or "") == "InlineBase64"
    ]
    if len(matches) != 1:
        raise E2EError(f"rdl_part_exact_count:{len(matches)}")
    payload = str(matches[0].get("payload") or "")
    try:
        return base64.b64decode(payload, validate=True).decode("utf-8")
    except Exception:
        raise E2EError("rdl_payload_invalid_base64") from None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _serialize_rdl_root(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8") + "\n"


def _style_with_no_border(parent: ET.Element) -> None:
    style = ET.SubElement(parent, report_factory._q("Style"))
    border = ET.SubElement(style, report_factory._q("Border"))
    value = ET.SubElement(border, report_factory._q("Style"))
    value.text = "None"


def _fabric_public_minimal_control(source_rdl: str) -> ET.Element:
    """Controle positivo RDL baseado na forma pública documentada pelo Fabric."""
    source = ET.fromstring(source_rdl)
    report_id = source.findtext(report_factory._rd("ReportID"), default="")
    if not report_id:
        raise E2EError("progressive_report_id_missing")

    root = ET.Element(report_factory._q("Report"), {"MustUnderstand": "df"})
    unit = ET.SubElement(root, report_factory._rd("ReportUnitType"))
    unit.text = "Inch"
    rid = ET.SubElement(root, report_factory._rd("ReportID"))
    rid.text = report_id
    font = ET.SubElement(root, report_factory._df("DefaultFontFamily"))
    font.text = "Segoe UI"
    refresh = ET.SubElement(root, report_factory._q("AutoRefresh"))
    refresh.text = "0"

    sections = ET.SubElement(root, report_factory._q("ReportSections"))
    section = ET.SubElement(sections, report_factory._q("ReportSection"))
    body = ET.SubElement(section, report_factory._q("Body"))
    items = ET.SubElement(body, report_factory._q("ReportItems"))
    title = ET.SubElement(items, report_factory._q("Textbox"), {"Name": "ReportTitle"})
    watermark = ET.SubElement(title, report_factory._rd("WatermarkTextbox"))
    watermark.text = "Title"
    default_name = ET.SubElement(title, report_factory._rd("DefaultName"))
    default_name.text = "ReportTitle"
    can_grow = ET.SubElement(title, report_factory._q("CanGrow"))
    can_grow.text = "true"
    keep = ET.SubElement(title, report_factory._q("KeepTogether"))
    keep.text = "true"
    paragraphs = ET.SubElement(title, report_factory._q("Paragraphs"))
    paragraph = ET.SubElement(paragraphs, report_factory._q("Paragraph"))
    runs = ET.SubElement(paragraph, report_factory._q("TextRuns"))
    run = ET.SubElement(runs, report_factory._q("TextRun"))
    value = ET.SubElement(run, report_factory._q("Value"))
    value.text = "ReqSys Fabric minimal control"
    run_style = ET.SubElement(run, report_factory._q("Style"))
    family = ET.SubElement(run_style, report_factory._q("FontFamily"))
    family.text = "Segoe UI Light"
    size = ET.SubElement(run_style, report_factory._q("FontSize"))
    size.text = "28pt"
    ET.SubElement(paragraph, report_factory._q("Style"))
    height = ET.SubElement(title, report_factory._q("Height"))
    height.text = "0.5in"
    width = ET.SubElement(title, report_factory._q("Width"))
    width.text = "5.5in"
    title_style = ET.SubElement(title, report_factory._q("Style"))
    border = ET.SubElement(title_style, report_factory._q("Border"))
    border_style = ET.SubElement(border, report_factory._q("Style"))
    border_style.text = "None"
    for tag in ("PaddingLeft", "PaddingRight", "PaddingTop", "PaddingBottom"):
        padding = ET.SubElement(title_style, report_factory._q(tag))
        padding.text = "2pt"

    body_height = ET.SubElement(body, report_factory._q("Height"))
    body_height.text = "2.25in"
    _style_with_no_border(body)

    section_width = ET.SubElement(section, report_factory._q("Width"))
    section_width.text = "6in"
    page = ET.SubElement(section, report_factory._q("Page"))
    footer = ET.SubElement(page, report_factory._q("PageFooter"))
    footer_height = ET.SubElement(footer, report_factory._q("Height"))
    footer_height.text = "0.45in"
    first = ET.SubElement(footer, report_factory._q("PrintOnFirstPage"))
    first.text = "true"
    last = ET.SubElement(footer, report_factory._q("PrintOnLastPage"))
    last.text = "true"
    footer_items = ET.SubElement(footer, report_factory._q("ReportItems"))
    execution = ET.SubElement(footer_items, report_factory._q("Textbox"), {"Name": "ExecutionTime"})
    execution_default = ET.SubElement(execution, report_factory._rd("DefaultName"))
    execution_default.text = "ExecutionTime"
    execution_grow = ET.SubElement(execution, report_factory._q("CanGrow"))
    execution_grow.text = "true"
    execution_keep = ET.SubElement(execution, report_factory._q("KeepTogether"))
    execution_keep.text = "true"
    execution_paragraphs = ET.SubElement(execution, report_factory._q("Paragraphs"))
    execution_paragraph = ET.SubElement(execution_paragraphs, report_factory._q("Paragraph"))
    execution_runs = ET.SubElement(execution_paragraph, report_factory._q("TextRuns"))
    execution_run = ET.SubElement(execution_runs, report_factory._q("TextRun"))
    execution_value = ET.SubElement(execution_run, report_factory._q("Value"))
    execution_value.text = "=Globals!ExecutionTime"
    ET.SubElement(execution_run, report_factory._q("Style"))
    execution_paragraph_style = ET.SubElement(execution_paragraph, report_factory._q("Style"))
    align = ET.SubElement(execution_paragraph_style, report_factory._q("TextAlign"))
    align.text = "Right"
    for tag, text in (("Top", "0.2in"), ("Left", "4in"), ("Height", "0.25in"), ("Width", "2in")):
        node = ET.SubElement(execution, report_factory._q(tag))
        node.text = text
    _style_with_no_border(execution)
    _style_with_no_border(footer)
    for tag in ("LeftMargin", "RightMargin", "TopMargin", "BottomMargin"):
        margin = ET.SubElement(page, report_factory._q(tag))
        margin.text = "1in"
    ET.SubElement(page, report_factory._q("Style"))

    layout = ET.SubElement(root, report_factory._q("ReportParametersLayout"))
    grid = ET.SubElement(layout, report_factory._q("GridLayoutDefinition"))
    columns = ET.SubElement(grid, report_factory._q("NumberOfColumns"))
    columns.text = "4"
    rows = ET.SubElement(grid, report_factory._q("NumberOfRows"))
    rows.text = "2"
    return root


def _insert_before_report_sections(root: ET.Element, node: ET.Element | None) -> None:
    if node is None:
        return
    sections = root.find(report_factory._q("ReportSections"))
    if sections is None:
        raise E2EError("progressive_report_sections_missing")
    root.insert(list(root).index(sections), copy.deepcopy(node))


def _progressive_rdl_variants(rdl: str) -> list[tuple[str, str]]:
    """Monta fases sobre um controle mínimo independente para isolar a primeira rejeição."""
    try:
        source = ET.fromstring(rdl)
    except ET.ParseError as exc:
        raise E2EError("progressive_source_rdl_invalid") from exc

    minimal = _fabric_public_minimal_control(rdl)

    datasource = copy.deepcopy(minimal)
    _insert_before_report_sections(datasource, source.find(report_factory._q("DataSources")))

    dataset = copy.deepcopy(datasource)
    _insert_before_report_sections(dataset, source.find(report_factory._q("DataSets")))
    _insert_before_report_sections(dataset, source.find(report_factory._q("ReportParameters")))
    source_layout = source.find(report_factory._q("ReportParametersLayout"))
    if source_layout is not None:
        current_layout = dataset.find(report_factory._q("ReportParametersLayout"))
        if current_layout is not None:
            dataset.remove(current_layout)
        dataset.append(copy.deepcopy(source_layout))

    return [
        ("minimal", _serialize_rdl_root(minimal)),
        ("datasource", _serialize_rdl_root(datasource)),
        ("dataset", _serialize_rdl_root(dataset)),
        ("full", rdl),
    ]


def _create_progressively(
    *,
    reports_url: str,
    workspace_id: str,
    report_name: str,
    description: str,
    rdl: str,
    token: str,
    evidence: dict[str, Any],
) -> None:
    """Cria o mesmo item uma vez e promove sua definição em camadas fail-closed."""
    variants = _progressive_rdl_variants(rdl)
    minimal_name, minimal_rdl = variants[0]
    if minimal_name != "minimal":
        raise E2EError("progressive_minimal_variant_missing")

    create_body: dict[str, Any] = {
        "displayName": report_name,
        "definition": report_factory.build_fabric_definition(report_name, minimal_rdl),
    }
    if description:
        create_body["description"] = description[:256]

    evidence["progressive_bootstrap_used"] = True
    evidence["progressive_passed_phases"] = []
    evidence["progressive_last_passed_phase"] = None
    evidence["progressive_failed_phase"] = None

    try:
        _invoke("POST", reports_url, token, create_body, success={200, 201})
    except E2EError as exc:
        evidence["progressive_failed_phase"] = "minimal_create"
        raise E2EError(f"progressive_minimal_create:{exc}") from None

    matches = _exact_by_display_name(_paged_values(reports_url, token), report_name, "report")
    if len(matches) != 1:
        evidence["progressive_failed_phase"] = "minimal_identity"
        raise E2EError(f"progressive_minimal_exact_count:{len(matches)}")
    report_id = str(matches[0].get("id") or "").strip()
    if not report_id:
        evidence["progressive_failed_phase"] = "minimal_identity"
        raise E2EError("progressive_minimal_report_id_missing")

    try:
        _verify_progressive_phase(
            workspace_id=workspace_id,
            report_id=report_id,
            report_name=report_name,
            phase="minimal",
            expected_rdl=minimal_rdl,
            token=token,
        )
    except E2EError as exc:
        evidence["progressive_failed_phase"] = "minimal"
        raise E2EError(f"progressive_minimal_readback:{exc}") from None
    evidence["progressive_passed_phases"].append("minimal")
    evidence["progressive_last_passed_phase"] = "minimal"

    for phase, phase_rdl in variants[1:]:
        try:
            _update_definition(
                workspace_id,
                report_id,
                report_factory.build_fabric_definition(report_name, phase_rdl),
                token,
            )
            _verify_progressive_phase(
                workspace_id=workspace_id,
                report_id=report_id,
                report_name=report_name,
                phase=phase,
                expected_rdl=phase_rdl,
                token=token,
            )
        except E2EError as exc:
            evidence["progressive_failed_phase"] = phase
            raise E2EError(f"progressive_{phase}:{exc}") from None
        evidence["progressive_passed_phases"].append(phase)
        evidence["progressive_last_passed_phase"] = phase


def _get_definition(workspace_id: str, report_id: str, token: str) -> dict[str, Any]:
    return _invoke(
        "POST",
        f"{FABRIC_BASE}/workspaces/{workspace_id}/paginatedReports/{report_id}/getDefinition?format=PaginatedReportDefinition",
        token,
        success={200},
        require_lro_result=True,
    )


def _verify_progressive_phase(
    *,
    workspace_id: str,
    report_id: str,
    report_name: str,
    phase: str,
    expected_rdl: str,
    token: str,
) -> None:
    observed_rdl = _extract_rdl(
        _get_definition(workspace_id, report_id, token),
        report_name,
    )
    if _sha256(observed_rdl) != _sha256(expected_rdl):
        raise E2EError(f"progressive_readback_hash_mismatch:{phase}")


def _update_definition(
    workspace_id: str, report_id: str, definition: dict[str, Any], token: str
) -> None:
    _invoke(
        "POST",
        f"{FABRIC_BASE}/workspaces/{workspace_id}/paginatedReports/{report_id}/updateDefinition",
        token,
        {"definition": definition},
        success={200},
    )


def execute(spec_path: Path, output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    correlation_id = (
        f"report-factory-{os.getenv('GITHUB_RUN_ID', 'local')}-"
        f"{os.getenv('GITHUB_RUN_ATTEMPT', '1')}"
    )
    evidence: dict[str, Any] = {
        "schema": "report-factory-fabric-dev-e2e/v1",
        "status": "blocked",
        "environment": ENVIRONMENT,
        "source_sha": os.getenv("GITHUB_SHA", ""),
        "correlation_id": correlation_id,
        "workspace_name": WORKSPACE_NAME,
        "workspace_exact_count": 0,
        "report_name": None,
        "initial_report_exact_count": None,
        "first_action": "none",
        "final_report_exact_count": None,
        "definition_verified": False,
        "idempotency_verified": False,
        "expected_rdl_sha256": None,
        "observed_rdl_sha256": None,
        "secret_value_exposed": False,
        "production_touched": False,
        "progressive_bootstrap_used": False,
        "progressive_passed_phases": [],
        "progressive_last_passed_phase": None,
        "progressive_failed_phase": None,
    }

    try:
        if os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("GITHUB_REF") != "refs/heads/main":
            raise E2EError("non_main_ref_blocked")
        if os.getenv("GITHUB_ACTIONS") == "true" and not evidence["source_sha"]:
            raise E2EError("source_sha_missing")

        spec = report_factory.load_spec(spec_path)
        report_factory.validate_spec(spec)
        report_name = str(spec["report"]["name"])
        evidence["report_name"] = report_name
        rdl = report_factory.generate_rdl(spec)
        report_factory.validate_rdl(rdl, spec)
        expected_hash = _sha256(rdl)
        evidence["expected_rdl_sha256"] = expected_hash
        definition = report_factory.build_fabric_definition(report_name, rdl)
        token = _fabric_token()

        workspaces = _paged_values(f"{FABRIC_BASE}/workspaces", token)
        workspace_matches = _exact_by_display_name(workspaces, WORKSPACE_NAME, "workspace")
        evidence["workspace_exact_count"] = len(workspace_matches)
        if len(workspace_matches) != 1:
            raise E2EError(f"workspace_exact_count:{len(workspace_matches)}")
        workspace_id = str(workspace_matches[0].get("id") or "").strip()
        if not workspace_id:
            raise E2EError("workspace_id_missing")

        reports_url = f"{FABRIC_BASE}/workspaces/{workspace_id}/paginatedReports"
        existing = _exact_by_display_name(_paged_values(reports_url, token), report_name, "report")
        evidence["initial_report_exact_count"] = len(existing)

        if not existing:
            description = str(spec["report"].get("description") or "").strip()
            _create_progressively(
                reports_url=reports_url,
                workspace_id=workspace_id,
                report_name=report_name,
                description=description,
                rdl=rdl,
                token=token,
                evidence=evidence,
            )
            evidence["first_action"] = "created_progressive"
        else:
            report_id = str(existing[0].get("id") or "").strip()
            if not report_id:
                raise E2EError("existing_report_id_missing")
            _update_definition(workspace_id, report_id, definition, token)
            evidence["first_action"] = "updated"

        final_matches = _exact_by_display_name(_paged_values(reports_url, token), report_name, "report")
        evidence["final_report_exact_count"] = len(final_matches)
        if len(final_matches) != 1:
            raise E2EError(f"final_report_exact_count:{len(final_matches)}")
        report_id = str(final_matches[0].get("id") or "").strip()
        if not report_id:
            raise E2EError("final_report_id_missing")

        observed_rdl = _extract_rdl(_get_definition(workspace_id, report_id, token), report_name)
        report_factory.validate_rdl(observed_rdl, spec)
        observed_hash = _sha256(observed_rdl)
        evidence["observed_rdl_sha256"] = observed_hash
        evidence["definition_verified"] = observed_hash == expected_hash
        if not evidence["definition_verified"]:
            raise E2EError("definition_hash_mismatch")

        _update_definition(workspace_id, report_id, definition, token)
        replay_matches = _exact_by_display_name(_paged_values(reports_url, token), report_name, "report")
        if len(replay_matches) != 1:
            raise E2EError(f"replay_report_exact_count:{len(replay_matches)}")
        replay_id = str(replay_matches[0].get("id") or "").strip()
        if replay_id != report_id:
            raise E2EError("replay_report_identity_changed")
        replay_rdl = _extract_rdl(_get_definition(workspace_id, report_id, token), report_name)
        evidence["idempotency_verified"] = _sha256(replay_rdl) == expected_hash
        if not evidence["idempotency_verified"]:
            raise E2EError("replay_definition_hash_mismatch")

        evidence["status"] = "passed"
        return 0
    except E2EError as exc:
        evidence["reason"] = str(exc)[:120]
        return 2
    except Exception as exc:
        evidence["reason"] = f"unexpected_{type(exc).__name__}"
        return 3
    finally:
        output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for key in (
            "status", "environment", "source_sha", "correlation_id", "workspace_name",
            "workspace_exact_count", "report_name", "initial_report_exact_count",
            "first_action", "final_report_exact_count", "definition_verified",
            "idempotency_verified", "expected_rdl_sha256", "observed_rdl_sha256",
            "secret_value_exposed", "production_touched",
            "progressive_bootstrap_used", "progressive_passed_phases",
            "progressive_last_passed_phase", "progressive_failed_phase", "reason",
        ):
            if key in evidence:
                print(f"{key}={evidence.get(key)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Publica e valida Report Factory no Fabric DEV")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/report-factory/fabric-dev-e2e.json"),
    )
    args = parser.parse_args()
    return execute(args.spec, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
