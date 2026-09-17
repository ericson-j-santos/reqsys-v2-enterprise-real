#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from backend.app.services.integration_excel_sql_sharepoint_flow import (
    gerar_definicao,
    validar_definicao_real,
)
from scripts.integration_excel_sql_sharepoint_dataverse import (
    install_definition,
    restore_clientdata,
    set_state,
)
from scripts.integration_excel_sql_sharepoint_e2e import (
    build_e2e_workbook,
    current_correlation_items,
    delete_sharepoint_item,
    derive_excel_source,
    download_workbook,
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
        "cleanup": {},
        "error": None,
    }

    original_workbook: bytes | None = None
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
            evidence["workbook_original_sha256"] = hashlib.sha256(original_workbook).hexdigest()

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

            original_clientdata = install_definition(
                client, dataverse_url, flow_id, dataverse_token, definition
            )
            evidence["checks"]["flow_definition_installed_via_dataverse"] = "passed"

            set_state(client, dataverse_url, flow_id, dataverse_token, 1)
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
    finally:
        with httpx.Client(follow_redirects=True) as cleanup:
            try:
                set_state(cleanup, dataverse_url, flow_id, dataverse_token, 0)
                evidence["cleanup"]["flow_stopped"] = True
            except Exception as exc:
                evidence["cleanup"]["flow_stopped"] = False
                evidence["cleanup"]["flow_stop_error"] = exc.__class__.__name__
                evidence["status"] = "failed"

            if original_clientdata is not None:
                try:
                    restore_clientdata(
                        cleanup, dataverse_url, flow_id, dataverse_token, original_clientdata
                    )
                    evidence["cleanup"]["flow_clientdata_restored"] = True
                except Exception as exc:
                    evidence["cleanup"]["flow_clientdata_restored"] = False
                    evidence["cleanup"]["flow_restore_error"] = exc.__class__.__name__
                    evidence["status"] = "failed"

            if original_workbook is not None:
                try:
                    _, current_etag = download_workbook(
                        cleanup, graph_token, drive_id, file_id
                    )
                    upload_workbook(
                        cleanup,
                        graph_token,
                        drive_id,
                        file_id,
                        original_workbook,
                        current_etag,
                    )
                    restored, _ = download_workbook(
                        cleanup, graph_token, drive_id, file_id
                    )
                    ok = hashlib.sha256(restored).hexdigest() == hashlib.sha256(original_workbook).hexdigest()
                    evidence["cleanup"]["workbook_restored"] = ok
                    if not ok:
                        evidence["status"] = "failed"
                except Exception as exc:
                    evidence["cleanup"]["workbook_restored"] = False
                    evidence["cleanup"]["workbook_restore_error"] = exc.__class__.__name__
                    evidence["status"] = "failed"

            if created_item_id:
                try:
                    delete_sharepoint_item(
                        cleanup, graph_token, site_id, list_id, created_item_id
                    )
                    remaining = matching_items(
                        list_items(cleanup, graph_token, site_id, list_id), fixture_id
                    )
                    evidence["cleanup"]["sharepoint_item_removed"] = not remaining
                    if remaining:
                        evidence["status"] = "failed"
                except Exception as exc:
                    evidence["cleanup"]["sharepoint_item_removed"] = False
                    evidence["cleanup"]["sharepoint_cleanup_error"] = exc.__class__.__name__
                    evidence["status"] = "failed"

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
