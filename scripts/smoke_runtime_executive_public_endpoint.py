#!/usr/bin/env python3
"""Smoke Runtime Executive public endpoint after deploy.

Validates the public Runtime Executive page and its JSON contract from a real
HTTP endpoint. The script is read-only, deterministic and safe for CI gates.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_PAGE_PATH = "/runtime-executive.html"
DEFAULT_CONTRACT_PATH = "/data/runtime-executive-index.json"
FORBIDDEN_HTML_SNIPPETS = {
    "api.github.com",
    "GITHUB_TOKEN",
    "Authorization",
    "github.com/repos",
}
REQUIRED_HTML_SNIPPETS = {
    "ReqSys Runtime Executive",
    "./data/runtime-executive-index.json",
    "fetch(CONTRACT_URL",
    "runtime-executive-cards",
    "runtime-executive-links",
    "no_runtime_github_api_call",
}
REQUIRED_GUARDRAILS = {
    "no_runtime_github_api_call",
    "official_runtime_executive_deeplink",
}


@dataclass(frozen=True)
class ProbeResult:
    url: str
    ok: bool
    status_code: int | None
    elapsed_ms: int
    error: str | None
    content: str


def normalize_base_url(value: str) -> str:
    base = value.strip()
    if not base:
        raise ValueError("base_url obrigatório")
    if not base.startswith(("http://", "https://")):
        raise ValueError("base_url deve iniciar com http:// ou https://")
    return base.rstrip("/") + "/"


def build_url(base_url: str, path: str) -> str:
    normalized_path = path.lstrip("/")
    return urljoin(base_url, normalized_path)


def fetch_text(url: str, timeout: float) -> ProbeResult:
    started = time.monotonic()
    request = Request(url, headers={"User-Agent": "ReqSys-RuntimeExecutiveSmoke/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - controlled read-only URL from CI input
            body = response.read().decode("utf-8", errors="replace")
            elapsed_ms = round((time.monotonic() - started) * 1000)
            status_code = getattr(response, "status", None)
            return ProbeResult(url, 200 <= int(status_code or 0) < 300, status_code, elapsed_ms, None, body)
    except HTTPError as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000)
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return ProbeResult(url, False, exc.code, elapsed_ms, f"HTTPError: {exc.code}", body)
    except (URLError, TimeoutError, OSError) as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000)
        return ProbeResult(url, False, None, elapsed_ms, f"{type(exc).__name__}: {exc}", "")


def validate_html(result: ProbeResult) -> list[str]:
    failures: list[str] = []
    if not result.ok:
        failures.append("runtime_executive_page_unavailable")
        return failures
    for snippet in REQUIRED_HTML_SNIPPETS:
        if snippet not in result.content:
            failures.append(f"html_missing_required_snippet:{snippet}")
    for snippet in FORBIDDEN_HTML_SNIPPETS:
        if snippet in result.content:
            failures.append(f"html_contains_forbidden_snippet:{snippet}")
    return failures


def validate_contract(result: ProbeResult) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    if not result.ok:
        return {}, ["runtime_executive_contract_unavailable"]
    try:
        payload = json.loads(result.content)
    except json.JSONDecodeError as exc:
        return {}, [f"runtime_executive_contract_invalid_json:{exc.msg}"]

    summary = payload.get("summary") or {}
    links = payload.get("links") or {}
    guardrails = set(payload.get("guardrails") or [])

    if summary.get("runtime_executive_page_published") is not True:
        failures.append("contract_summary_page_not_published")
    if "runtime_executive_page" not in links:
        failures.append("contract_missing_runtime_executive_page_link")
    if "runtime_executive_index" not in links:
        failures.append("contract_missing_runtime_executive_index_link")

    missing_guardrails = sorted(REQUIRED_GUARDRAILS - guardrails)
    for guardrail in missing_guardrails:
        failures.append(f"contract_missing_guardrail:{guardrail}")

    return payload, failures


def run_probe(base_url: str, page_path: str, contract_path: str, timeout: float) -> dict[str, Any]:
    normalized_base = normalize_base_url(base_url)
    page_url = build_url(normalized_base, page_path)
    contract_url = build_url(normalized_base, contract_path)

    page_result = fetch_text(page_url, timeout)
    contract_result = fetch_text(contract_url, timeout)
    contract_payload, contract_failures = validate_contract(contract_result)

    failures = [*validate_html(page_result), *contract_failures]
    status = "passed" if not failures else "failed"

    return {
        "schema_version": "1.0.0",
        "contract": "runtime-executive-post-deploy-smoke",
        "validated_at_epoch": int(time.time()),
        "status": status,
        "ok": status == "passed",
        "base_url": normalized_base.rstrip("/"),
        "page_url": page_url,
        "contract_url": contract_url,
        "failures": failures,
        "checks": {
            "page": {
                "ok": page_result.ok,
                "status_code": page_result.status_code,
                "elapsed_ms": page_result.elapsed_ms,
                "error": page_result.error,
            },
            "contract": {
                "ok": contract_result.ok,
                "status_code": contract_result.status_code,
                "elapsed_ms": contract_result.elapsed_ms,
                "error": contract_result.error,
                "executive_score": (contract_payload.get("summary") or {}).get("executive_score"),
                "risk": (contract_payload.get("summary") or {}).get("risk"),
            },
        },
        "guardrails": [
            "read_only_http_probe",
            "no_secret_required",
            "strict_gate_optional",
            "dev_stg_prod_url_parameterized",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke Runtime Executive public endpoint after deploy")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--page-path", default=DEFAULT_PAGE_PATH)
    parser.add_argument("--contract-path", default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output", default="artifacts/runtime-executive-post-deploy-smoke/runtime-executive-post-deploy-smoke.json")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    payload = run_probe(args.base_url, args.page_path, args.contract_path, args.timeout)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if args.strict and not payload["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
