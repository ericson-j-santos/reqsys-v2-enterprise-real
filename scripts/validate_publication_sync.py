#!/usr/bin/env python3
"""Valida se o runtime publicado (Fly.io) está sincronizado com o repositório.

Read-only: compara SHA/version local com evidências públicas da API e frontend,
sem credenciais e sem deploy.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "infra" / "fly-environments.json"
DEFAULT_PACKAGE_JSON = ROOT / "frontend" / "package.json"


@dataclass(frozen=True)
class ComponentSync:
    component: str
    reachable: bool
    synced: bool
    expected: str
    observed: str | None
    detail: str | None = None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _local_git_sha() -> str:
    for key in ("GITHUB_SHA", "CI_COMMIT_SHA"):
        value = __import__("os").environ.get(key, "").strip()
        if value:
            return value[:12]
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()[:12]
    except Exception:
        return "unknown"


def _local_version() -> str:
    if DEFAULT_PACKAGE_JSON.exists():
        payload = _read_json(DEFAULT_PACKAGE_JSON)
        version = str(payload.get("version") or "").strip()
        if version:
            return version
    return "unknown"


def _http_json(url: str, timeout: float) -> tuple[dict[str, Any] | None, str | None]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "reqsys-publication-sync/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        return None, str(exc)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"json_invalid: {exc}"
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            return data, None
        return payload, None
    return None, "payload_not_object"


def _http_head_last_modified(url: str, timeout: float) -> tuple[str | None, str | None]:
    request = Request(url, method="HEAD", headers={"User-Agent": "reqsys-publication-sync/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.headers.get("Last-Modified"), None
    except (HTTPError, URLError, TimeoutError) as exc:
        return None, str(exc)


def _http_text(url: str, timeout: float) -> tuple[str | None, str | None]:
    request = Request(url, headers={"User-Agent": "reqsys-publication-sync/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read(256_000).decode("utf-8", errors="ignore"), None
    except (HTTPError, URLError, TimeoutError) as exc:
        return None, str(exc)


def _extract_frontend_asset_hash(html: str | None) -> str | None:
    if not html:
        return None
    match = re.search(r"/assets/index-([A-Za-z0-9_-]+)\.js", html)
    return match.group(1) if match else None


def _normalize_sha(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    match = re.search(r"([0-9a-f]{7,40})", cleaned, flags=re.IGNORECASE)
    if match:
        return match.group(1)[:12]
    return cleaned[:12]


def _sha_matches(expected: str, observed: str | None) -> bool:
    if not observed or expected == "unknown":
        return False
    return _normalize_sha(observed) == _normalize_sha(expected)


def _fetch_origin_main_sha() -> str | None:
    try:
        subprocess.run(
            ["git", "fetch", "origin", "main", "--depth", "1"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        completed = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return _normalize_sha(completed.stdout.strip())
    except Exception:
        return None


def _api_sha_acceptable(expected_sha: str, observed_sha: str | None) -> tuple[bool, str]:
    if _sha_matches(expected_sha, observed_sha):
        return True, "matches_event_sha"
    main_head = _fetch_origin_main_sha()
    if main_head and _sha_matches(main_head, observed_sha):
        return True, "matches_origin_main_head"
    return False, "sha_mismatch"


def validate_environment(
    env_name: str,
    cfg: dict[str, Any],
    *,
    expected_sha: str,
    expected_version: str,
    timeout: float,
) -> dict[str, Any]:
    api_url = str(cfg["api_url"]).rstrip("/")
    frontend_url = str(cfg["frontend_url"]).rstrip("/")

    build_info, build_error = _http_json(f"{api_url}/api/runtime/build-info", timeout)
    version_info, _ = _http_json(f"{api_url}/api/runtime/version", timeout)
    health_info, health_error = _http_json(f"{api_url}/health", timeout)
    frontend_html, frontend_error = _http_text(f"{frontend_url}/", timeout)
    frontend_modified, _ = _http_head_last_modified(f"{frontend_url}/", timeout)

    observed_sha = None
    observed_version = None
    if build_info:
        observed_sha = str(build_info.get("build_sha") or build_info.get("commit_sha") or "")
    if version_info:
        observed_version = str(version_info.get("version") or "")

    api_reachable = health_info is not None and health_error is None
    frontend_reachable = frontend_html is not None and frontend_error is None
    sha_ok, sync_reason = _api_sha_acceptable(expected_sha, observed_sha)
    api_synced = api_reachable and sha_ok and (
        not observed_version or observed_version == expected_version
    )
    frontend_asset = _extract_frontend_asset_hash(frontend_html)

    components = [
        ComponentSync(
            component="api",
            reachable=api_reachable,
            synced=api_synced,
            expected=f"sha={expected_sha} version={expected_version}",
            observed=f"sha={observed_sha or 'n/a'} version={observed_version or 'n/a'}",
            detail=health_error or build_error,
        ),
        ComponentSync(
            component="frontend",
            reachable=frontend_reachable,
            synced=frontend_reachable,
            expected=f"publicado em {frontend_url}",
            observed=f"asset={frontend_asset or 'n/a'} last_modified={frontend_modified or 'n/a'}",
            detail=frontend_error,
        ),
    ]

    blocking_issues: list[str] = []
    if not api_reachable:
        blocking_issues.append(f"API indisponível em {api_url}: {health_error or build_error or 'sem resposta'}")
    elif not api_synced:
        blocking_issues.append(
            f"API dessincronizada: esperado sha={expected_sha} version={expected_version}, "
            f"observado sha={observed_sha or 'n/a'} version={observed_version or 'n/a'}"
        )
    if not frontend_reachable:
        blocking_issues.append(f"Frontend indisponível em {frontend_url}: {frontend_error or 'sem resposta'}")

    operational_status = "synced"
    if blocking_issues:
        operational_status = "out_of_sync" if api_reachable or frontend_reachable else "unavailable"

    return {
        "environment": env_name,
        "api_url": api_url,
        "frontend_url": frontend_url,
        "expected": {"sha": expected_sha, "version": expected_version},
        "observed": {
            "sha": observed_sha,
            "version": observed_version,
            "frontend_asset": frontend_asset,
            "frontend_last_modified": frontend_modified,
            "sync_reason": sync_reason if api_reachable else None,
        },
        "components": [asdict(item) for item in components],
        "operational_status": operational_status,
        "synced": not blocking_issues,
        "blocking_issues": blocking_issues,
    }


def build_payload(
    *,
    manifest_path: Path,
    environment: str | None,
    expected_sha: str,
    expected_version: str,
    timeout: float,
) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    environments = manifest.get("environments") or {}
    targets = [environment] if environment else list(manifest.get("canonical_environments") or environments.keys())

    summaries = []
    for env_name in targets:
        cfg = environments.get(env_name)
        if not cfg:
            continue
        summaries.append(
            validate_environment(
                env_name,
                cfg,
                expected_sha=expected_sha,
                expected_version=expected_version,
                timeout=timeout,
            )
        )

    blocking = [issue for summary in summaries for issue in summary.get("blocking_issues", [])]
    return {
        "schema_version": "1.0.0",
        "contract": "publication-sync-validation",
        "validated_at_epoch": int(time.time()),
        "repository": {
            "sha": expected_sha,
            "version": expected_version,
        },
        "environments": summaries,
        "ok": not blocking,
        "blocking_issues": blocking,
        "next_actions": [
            "Executar workflow Deploy Production Sync com approve_prod_deploy=APROVO-PROD",
            "Validar secrets Fly (JWT_ISSUER, JWT_AUDIENCE, AZURE_*) no app reqsys-api",
            "Reexecutar este validador após o deploy",
        ]
        if blocking
        else ["Publicação sincronizada com o repositório"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida sincronização repo ↔ runtime publicado")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--environment", choices=["dev", "hml", "prod"], help="Ambiente alvo (default: todos)")
    parser.add_argument("--expected-sha", default=_local_git_sha())
    parser.add_argument("--expected-version", default=_local_version())
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--output", help="Arquivo JSON de evidência")
    args = parser.parse_args()

    payload = build_payload(
        manifest_path=Path(args.manifest),
        environment=args.environment,
        expected_sha=args.expected_sha,
        expected_version=args.expected_version,
        timeout=args.timeout,
    )
    if args.output:
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
