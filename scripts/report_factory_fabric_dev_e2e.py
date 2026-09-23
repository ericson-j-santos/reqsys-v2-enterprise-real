#!/usr/bin/env python3
"""E2E governado do ReqSys Report Factory no Microsoft Fabric DEV."""

from __future__ import annotations

import argparse
import base64
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


def _safe_error_token(value: Any) -> str | None:
    """Normaliza um código de erro sem carregar mensagem, parâmetros ou IDs."""
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    normalized = normalized.strip("_.-")[:80]
    return normalized or None


def _safe_fabric_error_signature(raw: str) -> str:
    """Extrai somente códigos estruturados estáveis do Fabric."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return "unknown"

    if not isinstance(payload, dict):
        return "unknown"

    candidates: list[Any] = [
        payload.get("errorCode"),
        payload.get("code"),
    ]
    nested = payload.get("error")
    if isinstance(nested, dict):
        candidates.extend([nested.get("errorCode"), nested.get("code")])

    main_code = next(
        (token for token in (_safe_error_token(item) for item in candidates) if token),
        "unknown",
    )

    detail_codes: list[str] = []
    more_details = payload.get("moreDetails")
    if isinstance(more_details, list):
        for item in more_details:
            if not isinstance(item, dict):
                continue
            token = _safe_error_token(item.get("errorCode"))
            if token and token not in detail_codes:
                detail_codes.append(token)
            if len(detail_codes) >= 5:
                break

    if not detail_codes:
        return main_code
    return f"{main_code}:{','.join(detail_codes)}"


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
        safe_signature = _safe_fabric_error_signature(raw)
        raise E2EError(f"fabric_http_{exc.code}:{safe_signature}") from None


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


def _get_definition(workspace_id: str, report_id: str, token: str) -> dict[str, Any]:
    return _invoke(
        "POST",
        f"{FABRIC_BASE}/workspaces/{workspace_id}/paginatedReports/{report_id}/getDefinition?format=PaginatedReportDefinition",
        token,
        success={200},
        require_lro_result=True,
    )


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
            _invoke(
                "POST",
                reports_url,
                token,
                report_factory.build_create_request(spec, rdl),
                success={200, 201},
            )
            evidence["first_action"] = "created"
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
            "secret_value_exposed", "production_touched", "reason",
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
