#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from scripts.integration_excel_sql_sharepoint_dataverse import (
    DataverseFlowError,
    get_flow,
    patch_flow,
)
from scripts.integration_excel_sql_sharepoint_e2e import (
    current_correlation_items,
    delete_sharepoint_item,
    download_workbook,
    graph_request,
    list_items,
)

T = TypeVar("T")


class CleanupError(RuntimeError):
    pass


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise CleanupError(f"variavel_obrigatoria_ausente:{name}")
    return value


def retry(
    operation: Callable[[], T],
    *,
    attempts: int,
    delay_seconds: int,
    retryable: Callable[[Exception], bool],
) -> T:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            last = exc
            if attempt >= attempts or not retryable(exc):
                raise
            time.sleep(delay_seconds)
    raise CleanupError(f"retry_exaurido:{type(last).__name__ if last else 'unknown'}")


def retryable_dataverse(exc: Exception) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, DataverseFlowError):
        return "http_429" in str(exc) or "http_5" in str(exc)
    return False


def ensure_flow_stopped(
    client: httpx.Client,
    dataverse_url: str,
    flow_id: str,
    token: str,
    *,
    attempts: int = 24,
    delay_seconds: int = 5,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            observed = get_flow(client, dataverse_url, flow_id, token)
            if int(observed.get("statecode", -1)) == 0:
                return observed
        except Exception as exc:
            last_error = exc

        try:
            patch_flow(client, dataverse_url, flow_id, token, {"statecode": 0})
        except Exception as exc:
            last_error = exc

        time.sleep(delay_seconds)

    try:
        observed = get_flow(client, dataverse_url, flow_id, token)
        if int(observed.get("statecode", -1)) == 0:
            return observed
    except Exception as exc:
        last_error = exc
    raise CleanupError(
        f"flow_stop_nao_confirmado:{type(last_error).__name__ if last_error else 'unknown'}"
    )


def restore_clientdata_with_retry(
    client: httpx.Client,
    dataverse_url: str,
    flow_id: str,
    token: str,
    original_clientdata: str,
    expected_sha256: str,
) -> None:
    ensure_flow_stopped(client, dataverse_url, flow_id, token)

    def do_patch() -> None:
        patch_flow(
            client,
            dataverse_url,
            flow_id,
            token,
            {"clientdata": original_clientdata},
        )

    retry(
        do_patch,
        attempts=12,
        delay_seconds=5,
        retryable=retryable_dataverse,
    )

    def verify() -> dict[str, Any]:
        observed = get_flow(client, dataverse_url, flow_id, token)
        raw = str(observed.get("clientdata") or "")
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != expected_sha256:
            raise CleanupError("flow_clientdata_hash_divergente")
        if int(observed.get("statecode", -1)) != 0:
            raise CleanupError("flow_statecode_divergente")
        return observed

    retry(
        verify,
        attempts=12,
        delay_seconds=5,
        retryable=lambda exc: isinstance(exc, (httpx.RequestError, CleanupError)),
    )


def restore_workbook_version(
    client: httpx.Client,
    token: str,
    drive_id: str,
    file_id: str,
    version_id: str,
    expected_sha256: str,
    *,
    attempts: int = 48,
    delay_seconds: int = 15,
) -> None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            current, _ = download_workbook(client, token, drive_id, file_id)
            if hashlib.sha256(current).hexdigest() == expected_sha256:
                return
        except Exception as exc:
            last_error = exc

        try:
            graph_request(
                client,
                "POST",
                f"/drives/{drive_id}/items/{file_id}/versions/{version_id}/restoreVersion",
                token,
            )
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code not in {409, 412, 423, 429} and exc.response.status_code < 500:
                raise
        except httpx.RequestError as exc:
            last_error = exc

        if attempt < attempts:
            time.sleep(delay_seconds)

    raise CleanupError(
        f"workbook_restore_nao_confirmado:{type(last_error).__name__ if last_error else 'unknown'}"
    )


def remove_correlation_items(
    client: httpx.Client,
    token: str,
    site_id: str,
    list_id: str,
    fixture_id: str,
    correlation_id: str,
) -> None:
    for _ in range(12):
        items = list_items(client, token, site_id, list_id)
        matches = current_correlation_items(items, fixture_id, correlation_id)
        if not matches:
            return
        for item in matches:
            item_id = str(item.get("id") or "").strip()
            if item_id:
                delete_sharepoint_item(client, token, site_id, list_id, item_id)
        time.sleep(3)
    raise CleanupError("sharepoint_residuo_nao_removido")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup deterministico do E2E OIDC DEV")
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    dataverse_url = required_env("INTEGRATION_E2E_DATAVERSE_URL")
    graph_token = required_env("POWER_PLATFORM_GRAPH_ACCESS_TOKEN")
    dataverse_token = required_env("POWER_PLATFORM_DATAVERSE_ACCESS_TOKEN")
    flow_id = required_env("INTEGRATION_E2E_FLOW_ID")
    drive_id = required_env("INTEGRATION_E2E_DRIVE_ID")
    file_id = required_env("INTEGRATION_E2E_FILE_ID")
    site_id = required_env("INTEGRATION_E2E_SITE_ID")
    list_id = required_env("INTEGRATION_E2E_LIST_ID")
    fixture_id = required_env("INTEGRATION_E2E_SQL_FIXTURE_ID")
    correlation_id = required_env("E2E_CORRELATION_ID")

    evidence: dict[str, Any] = {
        "schema_version": "1.0.0",
        "feature": "excel_sql_sharepoint_oidc_cleanup",
        "environment": "dev",
        "correlation_id": correlation_id,
        "status": "running",
        "checks": {},
        "error": None,
    }

    state: dict[str, Any] = {}
    if args.state.exists():
        state = json.loads(args.state.read_text(encoding="utf-8"))

    try:
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            flow = ensure_flow_stopped(
                client, dataverse_url, flow_id, dataverse_token
            )
            evidence["checks"]["flow_stopped"] = int(flow.get("statecode", -1)) == 0

            if state.get("original_clientdata"):
                restore_clientdata_with_retry(
                    client,
                    dataverse_url,
                    flow_id,
                    dataverse_token,
                    str(state["original_clientdata"]),
                    str(state["original_clientdata_sha256"]),
                )
                evidence["checks"]["flow_clientdata_restored"] = True
            else:
                evidence["checks"]["flow_clientdata_restored"] = "not_required"

            if state.get("workbook_original_version_id"):
                restore_workbook_version(
                    client,
                    graph_token,
                    drive_id,
                    file_id,
                    str(state["workbook_original_version_id"]),
                    str(state["workbook_original_sha256"]),
                )
                evidence["checks"]["workbook_restored"] = True
            else:
                evidence["checks"]["workbook_restored"] = "not_required"

            remove_correlation_items(
                client,
                graph_token,
                site_id,
                list_id,
                fixture_id,
                correlation_id,
            )
            evidence["checks"]["sharepoint_residual_absent"] = True

            final_flow = get_flow(client, dataverse_url, flow_id, dataverse_token)
            evidence["checks"]["flow_statecode_zero"] = int(final_flow.get("statecode", -1)) == 0

            if state.get("original_clientdata_sha256"):
                observed_hash = hashlib.sha256(
                    str(final_flow.get("clientdata") or "").encode("utf-8")
                ).hexdigest()
                evidence["checks"]["flow_clientdata_hash_match"] = (
                    observed_hash == str(state["original_clientdata_sha256"])
                )

            if state.get("workbook_original_sha256"):
                workbook, _ = download_workbook(client, graph_token, drive_id, file_id)
                evidence["checks"]["workbook_hash_match"] = (
                    hashlib.sha256(workbook).hexdigest()
                    == str(state["workbook_original_sha256"])
                )

            remaining = current_correlation_items(
                list_items(client, graph_token, site_id, list_id),
                fixture_id,
                correlation_id,
            )
            evidence["checks"]["sharepoint_final_read_zero"] = len(remaining) == 0

            failed = [name for name, value in evidence["checks"].items() if value is False]
            if failed:
                raise CleanupError("verificacao_final_falhou:" + ",".join(sorted(failed)))
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
        "error": evidence["error"],
    }, ensure_ascii=False))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
