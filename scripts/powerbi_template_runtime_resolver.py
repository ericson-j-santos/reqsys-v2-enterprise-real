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
from collections import Counter
from pathlib import Path
from typing import Any, Callable

EXPECTED_TENANT = "6d09c88c-0617-490c-8329-305e577684bc"
POWERBI_RESOURCE = "https://analysis.windows.net/powerbi/api"
FABRIC_RESOURCE = "https://api.fabric.microsoft.com"
POWERBI_BASE = "https://api.powerbi.com/v1.0/myorg"
FABRIC_BASE = "https://api.fabric.microsoft.com/v1"
_GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_ALLOWED_GET = re.compile(
    r"^/v1\.0/myorg/(?:groups|groups/[0-9a-fA-F-]{36}/(?:reports|datasets|users))$"
)
_ALLOWED_POST = re.compile(
    r"^/v1\.0/myorg/groups/[0-9a-fA-F-]{36}/datasets/[0-9a-fA-F-]{36}/executeQueries$"
)
_ALLOWED_FABRIC_GET = re.compile(
    r"^/v1/(?:workspaces|workspaces/[0-9a-fA-F-]{36}/roleAssignments)$"
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


def _token(resource: str) -> str:
    return _az_tsv([
        "account", "get-access-token",
        "--resource", resource,
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
_DOMAIN_SIGNATURES = {
    "dre": (frozenset({"dre"}), frozenset({"v2"})),
    "rh": (frozenset({"rh"}), frozenset({"v2"})),
    "estoque": (frozenset({"estoque"}), frozenset({"v2"})),
    "sac": (frozenset({"sac"}), frozenset({"v2"})),
    "logistica": (frozenset({"logistica"}), frozenset({"v2"})),
    "financeiro": (frozenset({"financeiro"}), frozenset({"v2"})),
    "comercial": (frozenset({"comercial"}), frozenset({"v2"})),
    "producao": (frozenset({"producao"}), frozenset({"v2"})),
    "producao_v2": (frozenset({"producao", "v2"}), frozenset()),
    "compras": (frozenset({"compras"}), frozenset({"v2"})),
    "compras_v2": (frozenset({"compras", "v2"}), frozenset()),
}


def _matching_templates(normalized: str) -> list[tuple[str, str]]:
    if not normalized:
        return []
    exact = [
        (template_id, "name_exact")
        for template_id, aliases in _NORMALIZED_ALIASES.items()
        if normalized in aliases
    ]
    if exact:
        return exact
    tokens = frozenset(normalized.split())
    matches = []
    for template_id, (required, forbidden) in _DOMAIN_SIGNATURES.items():
        if required <= tokens and not (forbidden & tokens):
            matches.append((template_id, "domain_signature"))
    return matches


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


def _fabric_request_json(
    method: str,
    url: str,
    bearer: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    if method != "GET" or payload is not None:
        raise ResolverError("fabric_method_not_allowed")
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "api.fabric.microsoft.com"
        or parsed.username
        or parsed.password
        or parsed.fragment
        or not _ALLOWED_FABRIC_GET.fullmatch(parsed.path)
    ):
        raise ResolverError("fabric_endpoint_not_allowed")
    if parsed.path == "/v1/workspaces":
        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if len(pairs) != 1 or pairs[0][0] != "roles" or pairs[0][1] not in {
            "Admin", "Member", "Contributor", "Viewer"
        }:
            raise ResolverError("fabric_query_not_allowed")
    elif parsed.query:
        raise ResolverError("fabric_query_not_allowed")
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {bearer}", "Accept": "application/json"},
        method="GET",
    )
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
            matches = _matching_templates(normalized)
            if len(matches) == 1:
                template_id, matching_mode = matches[0]
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
                current["basis"].add(
                    "report_name_exact"
                    if matching_mode == "name_exact"
                    else "report_domain_signature"
                )
                if dataset_id in dataset_ids:
                    current["basis"].add("dataset_visible")
        for dataset in datasets or []:
            dataset_id = _valid_guid(dataset.get("id"))
            normalized = _normalize_name(dataset.get("name"))
            if dataset_id is None:
                continue
            matches = _matching_templates(normalized)
            if len(matches) == 1:
                template_id, matching_mode = matches[0]
                current = candidates[template_id].setdefault(
                    dataset_id,
                    {
                        "workspace_id": workspace_id,
                        "dataset_id": dataset_id,
                        "report_ids": set(),
                        "basis": set(),
                    },
                )
                current["basis"].add(
                    "dataset_name_exact"
                    if matching_mode == "name_exact"
                    else "dataset_domain_signature"
                )

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
        # Não anexar payload/erro remoto, que pode conter dados privados.
        raise ResolverError("execute_queries_response_invalid") from None
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
    principal_identifier: str | None = None,
    fabric_token: str | None = None,
    requester: Requester = _request_json,
    fabric_requester: Requester = _fabric_request_json,
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
    workspace_access: list[dict[str, Any]] = []
    fabric_role_workspace_ids: dict[str, set[str]] = {}
    fabric_role_filter_status: dict[str, int] = {}
    if fabric_token:
        for candidate_role in ("Admin", "Member", "Contributor", "Viewer"):
            role_status, role_payload = fabric_requester(
                "GET",
                f"{FABRIC_BASE}/workspaces?roles={candidate_role}",
                fabric_token,
                None,
            )
            fabric_role_filter_status[candidate_role] = role_status
            events.append({
                "category": f"fabric_workspaces_role_{candidate_role.casefold()}",
                "method": "GET",
                "status": role_status,
            })
            ids: set[str] = set()
            if role_status == 200 and isinstance(role_payload.get("value"), list):
                for item in role_payload["value"]:
                    if isinstance(item, dict):
                        identifier = _valid_guid(item.get("id"))
                        if identifier:
                            ids.add(identifier)
            fabric_role_workspace_ids[candidate_role] = ids

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
        users = _collection(
            requester, token, f"{POWERBI_BASE}/groups/{workspace_id}/users",
            events, "workspace_users",
        )
        principal_roles = []
        if principal_identifier and users is not None:
            for item in users:
                identifier = item.get("identifier")
                principal_type = item.get("principalType")
                role = item.get("groupUserAccessRight")
                if (
                    isinstance(identifier, str)
                    and identifier.casefold() == principal_identifier.casefold()
                    and principal_type == "App"
                    and role in {"Admin", "Member", "Contributor", "Viewer", "None"}
                ):
                    principal_roles.append(role)
        role = principal_roles[0] if len(principal_roles) == 1 else None
        is_read_only = group.get("isReadOnly") if type(group.get("isReadOnly")) is bool else None
        is_dedicated = (
            group.get("isOnDedicatedCapacity")
            if type(group.get("isOnDedicatedCapacity")) is bool else None
        )
        capacity_id = _valid_guid(group.get("capacityId"))
        fabric_role = None
        fabric_role_status = "unobserved"
        fabric_role_assignments_status = None
        if fabric_token and principal_identifier:
            fabric_status, fabric_payload = fabric_requester(
                "GET",
                f"{FABRIC_BASE}/workspaces/{workspace_id}/roleAssignments",
                fabric_token,
                None,
            )
            fabric_role_assignments_status = fabric_status
            events.append({
                "category": "fabric_role_assignments",
                "method": "GET",
                "status": fabric_status,
            })
            if fabric_status == 200:
                values = fabric_payload.get("value")
                if isinstance(values, list):
                    matched_roles = []
                    for assignment in values:
                        if not isinstance(assignment, dict):
                            continue
                        principal = assignment.get("principal")
                        if not isinstance(principal, dict):
                            continue
                        details = principal.get("servicePrincipalDetails")
                        app_id = details.get("aadAppId") if isinstance(details, dict) else None
                        fabric_assignment_role = assignment.get("role")
                        if (
                            principal.get("type") == "ServicePrincipal"
                            and isinstance(app_id, str)
                            and app_id.casefold() == principal_identifier.casefold()
                            and fabric_assignment_role in {"Admin", "Member", "Contributor", "Viewer"}
                        ):
                            matched_roles.append(fabric_assignment_role)
                    if len(matched_roles) == 1:
                        fabric_role = matched_roles[0]
                        fabric_role_status = "observed"
                    elif len(matched_roles) > 1:
                        fabric_role_status = "ambiguous"
                    else:
                        fabric_role_status = "not_found"
                else:
                    fabric_role_status = "invalid_contract"
            elif fabric_status == 403:
                fabric_role_status = "forbidden"
            elif fabric_status == 401:
                fabric_role_status = "unauthorized"
            else:
                fabric_role_status = "unobserved"

        role_filter_matches = [
            candidate_role
            for candidate_role, ids in fabric_role_workspace_ids.items()
            if workspace_id in ids
        ]
        fabric_filter_role = role_filter_matches[0] if len(role_filter_matches) == 1 else None
        fabric_filter_role_status = (
            "observed"
            if len(role_filter_matches) == 1
            else "ambiguous"
            if len(role_filter_matches) > 1
            else "not_found"
            if fabric_token and all(
                status == 200 for status in fabric_role_filter_status.values()
            )
            else "unobserved"
        )
        effective_role = fabric_filter_role or fabric_role or role
        workspace_access.append({
            "workspace_ref": _ref(workspace_id),
            "is_read_only": is_read_only,
            "is_on_dedicated_capacity": is_dedicated,
            "capacity_ref": _ref(capacity_id) if capacity_id else None,
            "default_dataset_storage_format": (
                group.get("defaultDatasetStorageFormat")
                if group.get("defaultDatasetStorageFormat") in {"Small", "Large"} else None
            ),
            "powerbi_principal_role": role,
            "powerbi_principal_role_status": (
                "observed"
                if len(principal_roles) == 1
                else "not_found"
                if users is not None and not principal_roles
                else "ambiguous"
                if len(principal_roles) > 1
                else "unobserved"
            ),
            "fabric_principal_role": fabric_role,
            "fabric_principal_role_status": fabric_role_status,
            "fabric_role_assignments_status": fabric_role_assignments_status,
            "fabric_role_filter_role": fabric_filter_role,
            "fabric_role_filter_status": fabric_filter_role_status,
            "fabric_role_filter_http": dict(fabric_role_filter_status),
            "effective_write_role": effective_role,
            "write_candidate": (
                effective_role in {"Admin", "Member", "Contributor"} and is_read_only is False
            ),
        })
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
        "workspace_access": workspace_access,
        "publication_preflight": {
            "existing_workspace_only": True,
            "new_capacity_or_license_requested": False,
            "billing_mutation_performed": False,
            "write_candidate_count": sum(
                1 for item in workspace_access if item["write_candidate"]
            ),
            "incremental_cost_verified_zero": False,
            "cost_verification_note": (
                "The API proves existing workspace/capacity flags and role only; "
                "it does not expose billing or prove zero incremental cost."
            ),
        },
        "sentinel_parity": sentinel,
        "metric_parity_promoted": False,
        "requests": events,
    }


def run(*, tenant_id: str, client_id: str, output: Path, requester: Requester = _request_json) -> dict[str, Any]:
    client_id = client_id.strip()
    tenant_id = tenant_id.strip()
    if not tenant_id or not client_id or _valid_guid(client_id) is None:
        raise ResolverError("oidc_configuration_missing")
    active_tenant = _az_tsv(["account", "show", "--query", "tenantId", "--output", "tsv"])
    tenant_match = active_tenant.casefold() == tenant_id.casefold() == EXPECTED_TENANT.casefold()
    if not tenant_match:
        raise ResolverError("tenant_mismatch")
    powerbi_token = _token(POWERBI_RESOURCE)
    fabric_token = _token(FABRIC_RESOURCE)
    evidence = resolve_runtime(
        token=powerbi_token,
        principal_identifier=client_id,
        fabric_token=fabric_token,
        requester=requester,
    )
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
    print(f"write_candidate_count={evidence['publication_preflight']['write_candidate_count']}")
    if evidence["workspace_access"]:
        workspace = evidence["workspace_access"][0]
        print(f"workspace_is_read_only={workspace['is_read_only']}")
        print(f"workspace_is_on_dedicated_capacity={workspace['is_on_dedicated_capacity']}")
        print(f"powerbi_workspace_principal_role={workspace['powerbi_principal_role']}")
        print(f"fabric_workspace_principal_role={workspace['fabric_principal_role']}")
        print(f"fabric_workspace_role_filter={workspace['fabric_role_filter_role']}")
        print(f"fabric_workspace_role_filter_status={workspace['fabric_role_filter_status']}")
        print(f"fabric_role_assignments_status={workspace['fabric_role_assignments_status']}")
    for status, count in sorted(evidence["binding_summary"].items()):
        print(f"binding_{status}={count}")
    print(f"sentinel_status={evidence['sentinel_parity']['status']}")
    print(f"mutations_performed={str(evidence['mutations_performed']).lower()}")
    print("raw_remote_ids_or_names_logged=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
