#!/usr/bin/env python3
"""Resolve os 11 templates Power BI no runtime OIDC sem persistir nomes ou IDs brutos.

A operação é somente leitura do ponto de vista do recurso. GET inventaria workspaces,
reports e datasets. POST é permitido exclusivamente para /executeQueries e somente
com uma consulta DAX fixa de sentinel, sem refresh/import/update/delete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

EXPECTED_TENANT = "6d09c88c-0617-490c-8329-305e577684bc"
POWERBI_RESOURCE = "https://analysis.windows.net/powerbi/api"
POWERBI_BASE = "https://api.powerbi.com/v1.0/myorg"
_GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_ALLOWED_GET = re.compile(
    r"^/v1\.0/myorg/(?:groups|groups/[0-9a-fA-F-]{36}/(?:reports|datasets))$"
)
_ALLOWED_POST = re.compile(
    r"^/v1\.0/myorg/groups/[0-9a-fA-F-]{36}/datasets/[0-9a-fA-F-]{36}/executeQueries$"
)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

TEMPLATE_ALIASES = {
    "dre": ("DRE", "Dashboard DRE", "1 Dashboard DRE"),
    "rh": ("RH", "Dashboard RH", "2 Dashboard RH"),
    "estoque": ("Estoque", "Dashboard Estoque", "3 Dashboard Estoque"),
    "sac": ("SAC", "Dashboard SAC", "4 Dashboard SAC"),
    "logistica": ("Logística", "Logistica", "Dashboard Logística", "Dashboard Logistica", "5 Dashboard Logistica"),
    "financeiro": ("Financeiro", "Dashboard Financeiro", "6 Dashboard Financeiro"),
    "comercial": ("Comercial", "Dashboard Comercial", "7 Dashboard Comercial"),
    "producao": ("Produção", "Producao", "Dashboard Produção", "Dashboard Producao", "8 Dashboard Producao"),
    "producao_v2": ("Produção V2", "Producao V2", "Produção - V2", "Producao - V2", "9 Producao V2"),
    "compras": ("Compras", "Dashboard Compras", "10 Dashboard Compras"),
    "compras_v2": ("Compras V2", "Compras - V2", "11 Compras V2"),
}

SENTINEL = {
    "template_id": "dre",
    "measure_table": "_Medidas",
    "measure_name": "Meta",
    "dax_expression": "0",
    "dax_query": 'EVALUATE ROW("value", \'_Medidas\'[Meta])',
    "web_value": 0,
    "representative_business_metric": False,
    "promotes_metric_parity": False,
}

Requester = Callable[[str, str, str, dict[str, Any] | None], tuple[int, dict[str, Any]]]


class ResolverError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _az(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["az", *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def _az_tsv(args: list[str]) -> str:
    result = _az(args)
    if result.returncode != 0:
        raise ResolverError("azure_cli_failed")
    value = (result.stdout or "").strip()
    if not value:
        raise ResolverError("azure_cli_empty")
    return value


def _token() -> str:
    return _az_tsv([
        "account", "get-access-token",
        "--resource", POWERBI_RESOURCE,
        "--query", "accessToken",
        "--output", "tsv",
        "--only-show-errors",
    ])


def _normalize_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"\.pbix$", "", text)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


_NORMALIZED_ALIASES = {
    template_id: frozenset(_normalize_name(alias) for alias in aliases)
    for template_id, aliases in TEMPLATE_ALIASES.items()
}


def _valid_guid(value: object) -> str | None:
    return str(value).lower() if isinstance(value, str) and _GUID.fullmatch(value) else None


def _ref(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()[:24]


def _validate_url(method: str, url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "api.powerbi.com"
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ResolverError("endpoint_not_allowed")
    if method == "GET":
        if not _ALLOWED_GET.fullmatch(parsed.path):
            raise ResolverError("endpoint_not_allowed")
        if parsed.path == "/v1.0/myorg/groups":
            pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            if pairs and (
                set(dict(pairs)) != {"$top", "$skip"}
                or any(not v.isdigit() for _, v in pairs)
            ):
                raise ResolverError("query_not_allowed")
        elif parsed.query:
            raise ResolverError("query_not_allowed")
        return
    if method == "POST" and _ALLOWED_POST.fullmatch(parsed.path) and not parsed.query:
        return
    raise ResolverError("method_not_allowed")


def _request_json(
    method: str,
    url: str,
    bearer: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    _validate_url(method, url)
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"Authorization": f"Bearer {bearer}", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ResolverError("response_too_large")
            try:
                decoded = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ResolverError("invalid_json") from exc
            return response.status, decoded if isinstance(decoded, dict) else {}
    except urllib.error.HTTPError as exc:
        exc.close()
        return exc.code, {}
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, {}


def _collection(
    requester: Requester,
    token: str,
    url: str,
    events: list[dict[str, Any]],
    category: str,
) -> list[dict[str, Any]] | None:
    status, payload = requester("GET", url, token, None)
    events.append({"category": category, "method": "GET", "status": status})
    if status != 200:
        return None
    values = payload.get("value")
    if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
        return None
    return values


def _resolve_candidates(
    inventory: list[tuple[str, list[dict[str, Any]] | None, list[dict[str, Any]] | None]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    candidates: dict[str, dict[str, dict[str, Any]]] = {
        template_id: {} for template_id in TEMPLATE_ALIASES
    }
    for workspace_id, reports, datasets in inventory:
        dataset_ids = {
            dataset_id
            for item in datasets or []
            if (dataset_id := _valid_guid(item.get("id"))) is not None
        }
        for report in reports or []:
            report_id = _valid_guid(report.get("id"))
            dataset_id = _valid_guid(report.get("datasetId"))
            normalized = _normalize_name(report.get("name"))
            if report_id is None or dataset_id is None:
                continue
            for template_id, aliases in _NORMALIZED_ALIASES.items():
                if normalized in aliases:
                    current = candidates[template_id].setdefault(
                        dataset_id,
                        {
                            "workspace_id": workspace_id,
                            "dataset_id": dataset_id,
                            "report_ids": set(),
                            "basis": set(),
                        },
                    )
                    current["report_ids"].add(report_id)
                    current["basis"].add("report_name_exact")
                    if dataset_id in dataset_ids:
                        current["basis"].add("dataset_visible")
        for dataset in datasets or []:
            dataset_id = _valid_guid(dataset.get("id"))
            normalized = _normalize_name(dataset.get("name"))
            if dataset_id is None:
                continue
            for template_id, aliases in _NORMALIZED_ALIASES.items():
                if normalized in aliases:
                    current = candidates[template_id].setdefault(
                        dataset_id,
                        {
                            "workspace_id": workspace_id,
                            "dataset_id": dataset_id,
                            "report_ids": set(),
                            "basis": set(),
                        },
                    )
                    current["basis"].add("dataset_name_exact")

    sanitized: list[dict[str, Any]] = []
    raw_bindings: dict[str, dict[str, str]] = {}
    for template_id in TEMPLATE_ALIASES:
        options = list(candidates[template_id].values())
        if not options:
            sanitized.append({"template_id": template_id, "status": "unmatched"})
            continue
        if len(options) != 1:
            sanitized.append({
                "template_id": template_id,
                "status": "ambiguous",
                "candidate_count": len(options),
            })
            continue
        option = options[0]
        report_ids = sorted(option["report_ids"])
        raw_bindings[template_id] = {
            "workspace_id": option["workspace_id"],
            "dataset_id": option["dataset_id"],
            "report_id": report_ids[0] if len(report_ids) == 1 else "",
        }
        sanitized.append({
            "template_id": template_id,
            "status": "resolved",
            "workspace_ref": _ref(option["workspace_id"]),
            "semantic_model_ref": _ref(option["dataset_id"]),
            "report_ref": _ref(report_ids[0]) if len(report_ids) == 1 else None,
            "match_basis": sorted(option["basis"]),
        })
    return sanitized, raw_bindings


def _extract_single_value(payload: dict[str, Any]) -> Any:
    try:
        rows = payload["results"][0]["tables"][0]["rows"]
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise KeyError
        row = rows[0]
        if "[value]" in row:
            return row["[value]"]
        if "value" in row:
            return row["value"]
        if len(row) == 1:
            return next(iter(row.values()))
    except (KeyError, IndexError, TypeError):
        pass
    raise ResolverError("execute_queries_response_invalid")


def _run_sentinel(
    requester: Requester,
    token: str,
    raw_bindings: dict[str, dict[str, str]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    binding = raw_bindings.get(SENTINEL["template_id"])
    base = {
        "template_id": SENTINEL["template_id"],
        "measure_table": SENTINEL["measure_table"],
        "measure_name": SENTINEL["measure_name"],
        "local_definition_sha256": hashlib.sha256(
            SENTINEL["dax_expression"].encode("utf-8")
        ).hexdigest(),
        "web_value": SENTINEL["web_value"],
        "representative_business_metric": False,
        "promotes_metric_parity": False,
    }
    if not binding:
        return {**base, "status": "blocked", "blocker": "dre_binding_unresolved"}
    url = (
        f"{POWERBI_BASE}/groups/{binding['workspace_id']}"
        f"/datasets/{binding['dataset_id']}/executeQueries"
    )
    status, payload = requester(
        "POST",
        url,
        token,
        {
            "queries": [{"query": SENTINEL["dax_query"]}],
            "serializerSettings": {"includeNulls": True},
        },
    )
    events.append({"category": "execute_queries_sentinel", "method": "POST", "status": status})
    if status != 200:
        return {
            **base,
            "status": "blocked",
            "blocker": "execute_queries_not_available",
            "http_status": status,
        }
    try:
        value = _extract_single_value(payload)
    except ResolverError as exc:
        return {**base, "status": "blocked", "blocker": str(exc), "http_status": status}
    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
    passed = numeric and float(value) == float(SENTINEL["web_value"])
    return {
        **base,
        "status": "passed" if passed else "failed",
        "http_status": status,
        "powerbi_value": value if numeric else None,
        "comparison": "exact_numeric",
    }


def resolve_runtime(
    *,
    token: str,
    requester: Requester = _request_json,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    seen: set[str] = set()
    page_size = 100
    for page in range(5):
        url = f"{POWERBI_BASE}/groups?$top={page_size}&$skip={page * page_size}"
        values = _collection(requester, token, url, events, "workspaces")
        if values is None:
            break
        for item in values:
            workspace_id = _valid_guid(item.get("id"))
            if workspace_id and workspace_id not in seen:
                seen.add(workspace_id)
                groups.append(item)
        if len(values) < page_size:
            break

    inventory = []
    report_count = dataset_count = 0
    for group in groups[:25]:
        workspace_id = _valid_guid(group.get("id"))
        if workspace_id is None:
            continue
        reports = _collection(
            requester, token, f"{POWERBI_BASE}/groups/{workspace_id}/reports",
            events, "reports",
        )
        datasets = _collection(
            requester, token, f"{POWERBI_BASE}/groups/{workspace_id}/datasets",
            events, "datasets",
        )
        report_count += len(reports or [])
        dataset_count += len(datasets or [])
        inventory.append((workspace_id, reports, datasets))

    bindings, raw_bindings = _resolve_candidates(inventory)
    sentinel = _run_sentinel(requester, token, raw_bindings, events)
    status_counts = Counter(item["status"] for item in bindings)
    return {
        "schema": "reqsys/powerbi-template-runtime-resolver/v1",
        "status": "completed",
        "operation": "read_only_inventory_and_execute_queries_sentinel",
        "mutations_performed": False,
        "secret_value_exposed": False,
        "raw_remote_ids_persisted": False,
        "raw_remote_names_persisted": False,
        "raw_remote_ids_or_names_logged": False,
        "catalog_template_count": len(TEMPLATE_ALIASES),
        "inventory": {
            "workspace_count": len(inventory),
            "report_count": report_count,
            "semantic_model_count": dataset_count,
        },
        "bindings": bindings,
        "binding_summary": dict(sorted(status_counts.items())),
        "sentinel_parity": sentinel,
        "metric_parity_promoted": False,
        "requests": events,
    }


def run(*, tenant_id: str, client_id: str, output: Path, requester: Requester = _request_json) -> dict[str, Any]:
    del client_id  # intentionally never persisted or logged
    tenant_id = tenant_id.strip()
    if not tenant_id:
        raise ResolverError("oidc_configuration_missing")
    active_tenant = _az_tsv(["account", "show", "--query", "tenantId", "--output", "tsv"])
    tenant_match = active_tenant.casefold() == tenant_id.casefold() == EXPECTED_TENANT.casefold()
    if not tenant_match:
        raise ResolverError("tenant_mismatch")
    token = _token()
    evidence = resolve_runtime(token=token, requester=requester)
    evidence["tenant_match"] = True
    evidence["correlation_id"] = str(uuid.uuid4())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = run(
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            output=args.output,
        )
    except (ResolverError, OSError, subprocess.SubprocessError) as exc:
        payload = {
            "schema": "reqsys/powerbi-template-runtime-resolver/v1",
            "status": "blocked",
            "blocker": str(exc).split(":", 1)[0],
            "mutations_performed": False,
            "secret_value_exposed": False,
            "raw_remote_ids_persisted": False,
            "raw_remote_names_persisted": False,
            "raw_remote_ids_or_names_logged": False,
            "metric_parity_promoted": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": "blocked", "blocker": payload["blocker"]}, sort_keys=True))
        return 2

    print("POWERBI_TEMPLATE_RUNTIME_RESOLVER_OK")
    print(f"tenant_match={str(evidence['tenant_match']).lower()}")
    print(f"workspace_count={evidence['inventory']['workspace_count']}")
    print(f"report_count={evidence['inventory']['report_count']}")
    print(f"semantic_model_count={evidence['inventory']['semantic_model_count']}")
    for status, count in sorted(evidence["binding_summary"].items()):
        print(f"binding_{status}={count}")
    print(f"sentinel_status={evidence['sentinel_parity']['status']}")
    print(f"mutations_performed={str(evidence['mutations_performed']).lower()}")
    print("raw_remote_ids_or_names_logged=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
