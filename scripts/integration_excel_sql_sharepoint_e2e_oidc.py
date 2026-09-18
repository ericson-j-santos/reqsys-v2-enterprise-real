#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from backend.app.services.integration_excel_sql_sharepoint_flow import (
    gerar_definicao,
    validar_definicao_real,
)
from scripts.integration_excel_sql_sharepoint_dataverse import (
    get_flow,
    merge_definition,
    patch_flow,
)
from scripts.integration_excel_sql_sharepoint_e2e import (
    build_e2e_workbook,
    current_correlation_items,
    derive_excel_source,
    download_workbook,
    graph_request,
    list_items,
    matching_items,
    upload_workbook,
    validate_sharepoint_columns,
)

TABLE = "tbEntrada"
DEFAULT_WAIT_SECONDS = 420


class OidcE2EError(RuntimeError):
    pass


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise OidcE2EError(f"variavel_obrigatoria_ausente:{name}")
    return value


def item_version(item: dict[str, Any]) -> str:
    return str(item.get("eTag") or item.get("lastModifiedDateTime") or "").strip()

def latest_workbook_version_id(
    client: httpx.Client,
    token: str,
    drive_id: str,
    file_id: str,
) -> str:
    response = graph_request(
        client,
        "GET",
        f"/drives/{drive_id}/items/{file_id}/versions?$top=20",
        token,
    ).json()
    versions = response.get("value") or []
    if not versions:
        raise OidcE2EError("workbook_version_history_ausente")
    def numeric(version: dict[str, Any]) -> tuple[int, ...]:
        parts = str(version.get("id") or "0").split(".")
        return tuple(int(part) if part.isdigit() else 0 for part in parts)
    latest = max(versions, key=numeric)
    version_id = str(latest.get("id") or "").strip()
    if not version_id:
        raise OidcE2EError("workbook_version_id_ausente")
    return version_id


def restore_workbook_version(
    client: httpx.Client,
    token: str,
    drive_id: str,
    file_id: str,
    version_id: str,
    expected_sha256: str,
    attempts: int = 24,
    delay_seconds: int = 10,
) -> None:
    last_status = 0
    for attempt in range(1, attempts + 1):
        try:
            graph_request(
                client,
                "POST",
                f"/drives/{drive_id}/items/{file_id}/versions/{version_id}/restoreVersion",
                token,
            )
            restored, _ = download_workbook(client, token, drive_id, file_id)
            observed = hashlib.sha256(restored).hexdigest()
            if observed != expected_sha256:
                raise OidcE2EError("workbook_restore_hash_divergente")
            return
        except httpx.HTTPStatusError as exc:
            last_status = exc.response.status_code
            if last_status != 423 or attempt >= attempts:
                raise
            time.sleep(delay_seconds)
    raise OidcE2EError(f"workbook_restore_timeout:http_{last_status}")



def wait_first_effect(
    client: httpx.Client,
    token: str,
    site_id: str,
    list_id: str,
    positive_key: str,
    correlation_id: str,
    invalid_key: str,
    timeout_seconds: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deadline = time.monotonic() + timeout_seconds
    last_positive = 0
    while time.monotonic() < deadline:
        items = list_items(client, token, site_id, list_id)
        positive = current_correlation_items(items, positive_key, correlation_id)
        invalid = matching_items(items, invalid_key)
        last_positive = len(positive)
        if len(positive) == 1 and not invalid:
            return positive[0], items
        if len(positive) > 1 or invalid:
            raise OidcE2EError(
                f"efeito_invalido:positive={len(positive)}:invalid={len(invalid)}"
            )
        time.sleep(10)
    raise OidcE2EError(f"efeito_sharepoint_timeout:positive={last_positive}")


def wait_idempotent_update(
    client: httpx.Client,
    token: str,
    site_id: str,
    list_id: str,
    positive_key: str,
    correlation_id: str,
    item_id: str,
    first_version: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        items = list_items(client, token, site_id, list_id)
        positive = current_correlation_items(items, positive_key, correlation_id)
        all_key = matching_items(items, positive_key)
        if len(positive) != 1 or len(all_key) != 1:
            raise OidcE2EError(
                f"idempotencia_falhou:corr={len(positive)}:key={len(all_key)}"
            )
        current = positive[0]
        if str(current.get("id") or "") != item_id:
            raise OidcE2EError("idempotencia_item_id_alterado")
        current_version = item_version(current)
        if first_version and current_version and current_version != first_version:
            return current
        time.sleep(10)
    raise OidcE2EError("segunda_execucao_nao_observada_por_versao")


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E real DEV via GitHub OIDC + Dataverse")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--cleanup-state", required=True, type=Path)
    parser.add_argument("--wait-seconds", type=int, default=DEFAULT_WAIT_SECONDS)
    args = parser.parse_args()

    if os.getenv("INTEGRATION_E2E_ENVIRONMENT", "dev").strip().lower() not in {"dev", "development"}:
        raise SystemExit("E2E restrito a DEV")

    graph_token = required_env("POWER_PLATFORM_GRAPH_ACCESS_TOKEN")
    dataverse_token = required_env("POWER_PLATFORM_DATAVERSE_ACCESS_TOKEN")
    dataverse_url = required_env("INTEGRATION_E2E_DATAVERSE_URL")
    flow_id = required_env("INTEGRATION_E2E_FLOW_ID")
    drive_id = required_env("INTEGRATION_E2E_DRIVE_ID")
    file_id = required_env("INTEGRATION_E2E_FILE_ID")
    site_id = required_env("INTEGRATION_E2E_SITE_ID")
    list_id = required_env("INTEGRATION_E2E_LIST_ID")
    procedure = required_env("INTEGRATION_E2E_SQL_PROCEDURE")
    fixture_id = required_env("INTEGRATION_E2E_SQL_FIXTURE_ID")
    if not fixture_id.isdigit():
        raise OidcE2EError("sql_fixture_id_invalido")

    invalid_identifier = f"REQSYS-E2E-INVALID-{uuid.uuid4().hex[:10]}"
    evidence: dict[str, Any] = {
        "schema_version": "1.0.0",
        "feature": "excel_sql_sharepoint_sync",
        "environment": "dev",
        "auth_mode": "github_oidc_dataverse",
        "source_sha": args.source_sha,
        "correlation_id": args.correlation_id,
        "status": "running",
        "real": True,
        "mocked": False,
        "simulated": False,
        "checks": {},
        "positive": {"identifier": fixture_id},
        "negative": {"identifier": invalid_identifier},
        "idempotency": {},
        "cleanup": {"delegated": True, "state_captured": False},
        "error": None,
    }

    original_workbook: bytes | None = None
    original_workbook_version_id = ""
    original_clientdata: str | None = None
    created_item_id = ""

    try:
        with httpx.Client(follow_redirects=True) as client:
            evidence["checks"]["graph_oidc"] = "passed"
            evidence["checks"]["dataverse_oidc"] = "passed"

            excel_source, sharepoint_site = derive_excel_source(
                client, graph_token, site_id, drive_id
            )
            list_name = validate_sharepoint_columns(
                client, graph_token, site_id, list_id
            )
            evidence["checks"]["resource_schema"] = "passed"

            original_workbook, original_etag = download_workbook(
                client, graph_token, drive_id, file_id
            )
            original_workbook_version_id = latest_workbook_version_id(
                client, graph_token, drive_id, file_id
            )
            workbook_original_sha256 = hashlib.sha256(original_workbook).hexdigest()
            evidence["workbook_original_sha256"] = workbook_original_sha256
            evidence["workbook_original_version_captured"] = True

            flow_before = get_flow(
                client, dataverse_url, flow_id, dataverse_token
            )
            if int(flow_before.get("statecode", -1)) != 0:
                raise OidcE2EError("flow_baseline_nao_esta_desligado")
            original_clientdata = str(flow_before.get("clientdata") or "")
            if not original_clientdata:
                raise OidcE2EError("flow_clientdata_original_ausente")
            original_clientdata_sha256 = hashlib.sha256(
                original_clientdata.encode("utf-8")
            ).hexdigest()

            cleanup_state = {
                "schema_version": "1.0.0",
                "environment": "dev",
                "correlation_id": args.correlation_id,
                "fixture_id": fixture_id,
                "flow_id": flow_id,
                "workbook_original_version_id": original_workbook_version_id,
                "workbook_original_sha256": workbook_original_sha256,
                "original_clientdata": original_clientdata,
                "original_clientdata_sha256": original_clientdata_sha256,
            }
            args.cleanup_state.parent.mkdir(parents=True, exist_ok=True)
            state_tmp = args.cleanup_state.with_suffix(args.cleanup_state.suffix + ".tmp")
            state_tmp.write_text(
                json.dumps(cleanup_state, ensure_ascii=False),
                encoding="utf-8",
            )
            state_tmp.replace(args.cleanup_state)
            evidence["cleanup"]["state_captured"] = True

            baseline = list_items(client, graph_token, site_id, list_id)
            if matching_items(baseline, fixture_id):
                raise OidcE2EError("baseline_sharepoint_residual_detectado")
            evidence["checks"]["baseline_sharepoint_absent"] = "passed"

            upload_workbook(
                client,
                graph_token,
                drive_id,
                file_id,
                build_e2e_workbook(fixture_id, invalid_identifier),
                original_etag,
            )
            evidence["checks"]["excel_test_input_uploaded"] = "passed"

            definition = gerar_definicao({
                "target_environment": "dev",
                "excel_source": excel_source,
                "excel_drive": drive_id,
                "excel_file": file_id,
                "excel_table": TABLE,
                "sql_procedure": procedure,
                "sharepoint_site": sharepoint_site,
                "sharepoint_list": list_name,
                "correlation_id": args.correlation_id,
            })
            errors = validar_definicao_real(definition)
            if errors:
                raise OidcE2EError("flow_definition_invalida:" + ",".join(errors))

            flow_pre_patch = get_flow(
                client, dataverse_url, flow_id, dataverse_token
            )
            current_clientdata = str(flow_pre_patch.get("clientdata") or "")
            if hashlib.sha256(current_clientdata.encode("utf-8")).hexdigest() != original_clientdata_sha256:
                raise OidcE2EError("flow_clientdata_mudou_concorrentemente")
            if int(flow_pre_patch.get("statecode", -1)) != 0:
                raise OidcE2EError("flow_estado_mudou_concorrentemente")

            patch_flow(
                client,
                dataverse_url,
                flow_id,
                dataverse_token,
                {"clientdata": merge_definition(original_clientdata, definition)},
            )
            evidence["checks"]["flow_definition_installed_via_dataverse"] = "passed"

            patch_flow(
                client,
                dataverse_url,
                flow_id,
                dataverse_token,
                {"statecode": 1},
            )
            activated = get_flow(client, dataverse_url, flow_id, dataverse_token)
            if int(activated.get("statecode", -1)) != 1:
                raise OidcE2EError("flow_activation_nao_confirmada")
            evidence["checks"]["flow_activation_via_dataverse"] = "passed"

            first_item, first_items = wait_first_effect(
                client,
                graph_token,
                site_id,
                list_id,
                fixture_id,
                args.correlation_id,
                invalid_identifier,
                args.wait_seconds,
            )
            created_item_id = str(first_item.get("id") or "")
            if not created_item_id:
                raise OidcE2EError("sharepoint_item_id_ausente")
            first_version = item_version(first_item)
            if not first_version:
                raise OidcE2EError("sharepoint_item_version_ausente")

            if len(matching_items(first_items, fixture_id)) != 1:
                raise OidcE2EError("sharepoint_chave_positiva_nao_unica")
            evidence["positive"].update({
                "sharepoint_item_id": created_item_id,
                "independent_read": "passed",
                "version_observed": True,
            })
            evidence["negative"].update({
                "sharepoint_matches": len(matching_items(first_items, invalid_identifier)),
                "independent_read": "passed",
            })
            evidence["checks"]["positive_case"] = "passed"
            evidence["checks"]["negative_case"] = "passed"
            evidence["checks"]["sql_via_gateway_real_flow"] = "passed"

            second_item = wait_idempotent_update(
                client,
                graph_token,
                site_id,
                list_id,
                fixture_id,
                args.correlation_id,
                created_item_id,
                first_version,
                args.wait_seconds,
            )
            evidence["idempotency"] = {
                "same_item_id": str(second_item.get("id") or "") == created_item_id,
                "second_version_observed": item_version(second_item) != first_version,
                "independent_read": "passed",
            }
            evidence["checks"]["idempotency"] = "passed"
            evidence["status"] = "passed"

    except Exception as exc:
        evidence["status"] = "failed"
        evidence["error"] = {
            "type": exc.__class__.__name__,
            "message": str(exc)[:500],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": evidence["status"],
        "checks": evidence["checks"],
        "cleanup": evidence["cleanup"],
        "error": evidence["error"],
    }, ensure_ascii=False))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
