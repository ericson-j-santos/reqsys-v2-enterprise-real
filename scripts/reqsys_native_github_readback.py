#!/usr/bin/env python3
"""Consulta oficial GitHub em executor independente; somente GET e sem secretos em logs.

O resultado observa runner e job. NÃO autentica identidade física do computador,
nem session_launcher/Gateway, nem assina recibos: esses gates são separados.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
API = f"https://api.github.com/repos/{REPO}"
SHA = re.compile(r"[a-f0-9]{40}\Z")
MAX_BYTES = 64 * 1024
TIMEOUT_SECONDS = 5


class GitHubReadbackBlocked(ValueError):
    pass


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise GitHubReadbackBlocked(code)


def _labels(raw: Any) -> list[str]:
    _require(isinstance(raw, list), "github_labels_invalid")
    values = [x.get("name") if isinstance(x, dict) else x for x in raw]
    _require(all(isinstance(v, str) and 0 < len(v) < 100 for v in values),
             "github_labels_invalid")
    _require(len(values) == len(set(v.casefold() for v in values)),
             "github_labels_ambiguous")
    return sorted(values, key=str.casefold)


def _github_get(path: str, *, token: str) -> dict[str, Any]:
    _require(isinstance(token, str) and len(token) >= 24 and "\n" not in token,
             "github_read_auth_unavailable")
    _require(bool(re.fullmatch(r"/(?:actions/(?:jobs|runners|runs))/[1-9][0-9]*", path)),
             "github_path_not_allowed")
    req = Request(
        API + path,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "reqsys-native-independent-readback/1.0",
        },
    )
    try:
        with urlopen(req, timeout=TIMEOUT_SECONDS) as response:  # nosec: B310 fixed allowlist
            _require(response.status == 200, "github_http_status_invalid")
            body = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise GitHubReadbackBlocked("github_readback_unavailable") from None
    _require(len(body) <= MAX_BYTES, "github_payload_oversized")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise GitHubReadbackBlocked("github_payload_invalid") from None
    _require(isinstance(value, dict), "github_payload_invalid")
    return value


def readback(*, run_id: int, job_id: int, runner_id: int,
             expected_sha: str, expected_labels: list[str], token: str,
             fetch: Callable[..., dict[str, Any]] = _github_get,
             at: datetime | None = None) -> dict[str, Any]:
    """Releitura externa, não certificado de prontidão física ou permissão.

    O caller deve verificar o contexto autenticado do executor GitHub-hosted.
    Não recebe host-id/instance-id porque a API GitHub não comprova essa relação.
    """
    _require(all(type(x) is int and x > 0 for x in (run_id, job_id, runner_id)),
             "github_ids_invalid")
    _require(isinstance(expected_sha, str) and SHA.fullmatch(expected_sha) is not None,
             "github_expected_sha_invalid")
    _require(isinstance(expected_labels, list) and expected_labels,
             "github_labels_invalid")
    run = fetch(f"/actions/runs/{run_id}", token=token)
    job = fetch(f"/actions/jobs/{job_id}", token=token)
    runner = fetch(f"/actions/runners/{runner_id}", token=token)
    _require(isinstance(run, dict) and isinstance(job, dict) and
             isinstance(runner, dict), "github_api_payload_invalid")
    _require(run.get("id") == run_id and run.get("head_sha") == expected_sha and
             run.get("repository", {}).get("full_name") == REPO,
             "github_run_mismatch")
    _require(job.get("id") == job_id and job.get("run_id") == run_id and
             job.get("runner_id") == runner_id and
             job.get("head_sha") == expected_sha,
             "github_job_mismatch")
    _require(runner.get("id") == runner_id and runner.get("status") == "online"
             and runner.get("busy") is False,
             "github_runner_not_idle")
    _require(_labels(job.get("labels")) == _labels(expected_labels) and
             _labels(runner.get("labels")) == _labels(expected_labels),
             "github_runner_labels_mismatch")
    _require(isinstance(job.get("runner_name"), str) and
             job["runner_name"] == runner.get("name"),
             "github_runner_name_mismatch")
    current = at or datetime.now(timezone.utc)
    _require(current.tzinfo is not None, "github_time_invalid")
    return {
        "source": "github_rest_independent_readback",
        "source_sha": expected_sha,
        "run_id": run_id,
        "job_id": job_id,
        "runner_id": runner_id,
        "runner_status": "online",
        "runner_busy": False,
        "runner_labels": _labels(expected_labels),
        "observed_at": current.astimezone(timezone.utc).isoformat(),
        "identity_binding_verified": False,
        "ready_for_work": False,
        "dispatch_allowed": False,
        "continuity_certified": False,
    }
