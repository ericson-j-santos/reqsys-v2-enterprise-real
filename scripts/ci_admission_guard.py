#!/usr/bin/env python3
"""Fail-fast guard para impedir CI caro sem manifesto Pre-PR do SHA exato e base atual."""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

SHA40 = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
WORKFLOW_NAME = "Pre-PR Readiness Gate"
WORKFLOW_FILE = "pre-pr-readiness.yml"
WORKFLOW_RUN_FALLBACK_MAX_PAGES = 5
MAX_ADMISSION_WAIT_SECONDS = 900
MAX_ADMISSION_POLL_SECONDS = 60
MANIFEST_SCHEMA_VERSION = "1.1.0"
REQUIRED_PREVENTIVE_INVARIANTS = {
    "sdd:contract",
    "security:changed-diff",
    "workflow:surface-budget",
    "workflow:regression-contracts",
}
RETRYABLE_REASONS = {
    "pre_pr_pending_for_head_sha",
    "pre_pr_success_missing_for_head_sha",
    "admission_manifest_missing_for_head_sha",
}


class AdmissionGuardError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def github_json(repository: str, path: str, token: str) -> dict[str, Any]:
    if not REPOSITORY_RE.fullmatch(repository):
        raise AdmissionGuardError("repository_invalid")
    if not token:
        raise AdmissionGuardError("github_token_missing")
    req = Request(
        f"https://api.github.com/repos/{repository}/{path.lstrip('/')}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        raise AdmissionGuardError(f"github_http_{exc.code}") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise AdmissionGuardError("github_unreachable_or_invalid") from exc
    if not isinstance(payload, dict):
        raise AdmissionGuardError("github_payload_invalid")
    return payload


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


def github_bytes(repository: str, path: str, token: str) -> bytes:
    """Baixa artifact sem encaminhar o bearer token ao host de redirect assinado."""
    if not REPOSITORY_RE.fullmatch(repository):
        raise AdmissionGuardError("repository_invalid")
    if not token:
        raise AdmissionGuardError("github_token_missing")

    api_url = f"https://api.github.com/repos/{repository}/{path.lstrip('/')}"
    req = Request(
        api_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    opener = build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=30) as response:
            return response.read()
    except HTTPError as exc:
        if exc.code not in {301, 302, 303, 307, 308}:
            raise AdmissionGuardError(f"github_http_{exc.code}") from exc
        location = str(exc.headers.get("Location") or "").strip()
        parsed = urlparse(location)
        if parsed.scheme != "https" or not parsed.netloc:
            raise AdmissionGuardError("artifact_redirect_invalid") from exc
        try:
            with urlopen(Request(location, headers={"Accept": "application/octet-stream"}), timeout=30) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as download_exc:
            raise AdmissionGuardError("artifact_download_failed") from download_exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AdmissionGuardError("github_unreachable_or_invalid") from exc


def validate_manifest_payload(manifest: dict[str, Any], head_sha: str, base_sha: str) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise AdmissionGuardError("admission_manifest_payload_invalid")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise AdmissionGuardError("admission_manifest_schema_invalid")
    if manifest.get("manifest_type") != "reqsys_ci_admission":
        raise AdmissionGuardError("admission_manifest_type_invalid")
    if manifest.get("status") != "admitted":
        raise AdmissionGuardError("admission_manifest_not_admitted")
    if str(manifest.get("head_sha") or "").lower() != head_sha:
        raise AdmissionGuardError("admission_manifest_head_sha_mismatch")
    if str(manifest.get("base_sha") or "").lower() != base_sha:
        raise AdmissionGuardError("admission_manifest_base_sha_mismatch")

    raw_invariants = manifest.get("preventive_invariants")
    if not isinstance(raw_invariants, list):
        raise AdmissionGuardError("admission_manifest_invariants_missing")
    statuses = {
        str(item.get("name") or ""): str(item.get("status") or "").lower()
        for item in raw_invariants
        if isinstance(item, dict)
    }
    missing_or_failed = [
        name for name in sorted(REQUIRED_PREVENTIVE_INVARIANTS)
        if statuses.get(name) != "passed"
    ]
    if missing_or_failed:
        raise AdmissionGuardError(
            "admission_manifest_invariants_failed:" + ",".join(missing_or_failed)
        )
    return {
        "schema_version": manifest["schema_version"],
        "status": manifest["status"],
        "head_sha": head_sha,
        "base_sha": base_sha,
        "preventive_invariants": [
            {"name": name, "status": statuses[name]}
            for name in sorted(REQUIRED_PREVENTIVE_INVARIANTS)
        ],
    }


def manifest_from_zip(data: bytes, head_sha: str) -> dict[str, Any]:
    expected_name = f"{head_sha}.json"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            matches = [
                name for name in archive.namelist()
                if not name.endswith("/") and PurePosixPath(name).name == expected_name
            ]
            if len(matches) != 1:
                raise AdmissionGuardError("admission_manifest_file_missing_or_ambiguous")
            payload = json.loads(archive.read(matches[0]).decode("utf-8"))
    except AdmissionGuardError:
        raise
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdmissionGuardError("admission_manifest_archive_invalid") from exc
    if not isinstance(payload, dict):
        raise AdmissionGuardError("admission_manifest_payload_invalid")
    return payload


def load_and_validate_manifest(
    repository: str,
    artifact: dict[str, Any],
    head_sha: str,
    base_sha: str,
    token: str,
) -> dict[str, Any]:
    artifact_id = int(artifact.get("id") or 0)
    if artifact_id < 1:
        raise AdmissionGuardError("admission_manifest_artifact_id_invalid")
    archive = github_bytes(repository, f"actions/artifacts/{artifact_id}/zip", token)
    manifest = manifest_from_zip(archive, head_sha)
    return validate_manifest_payload(manifest, head_sha, base_sha)


def successful_pre_pr_runs(
    runs: list[dict[str, Any]],
    head_sha: str,
    pr_number: int,
) -> list[dict[str, Any]]:
    return sorted(
        [
            run for run in runs
            if run_matches_pull_request(run, head_sha, pr_number)
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
        ],
        key=lambda item: str(item.get("updated_at") or ""),
        reverse=True,
    )


def run_matches_pull_request(run: Any, head_sha: str, pr_number: int) -> bool:
    if (
        not isinstance(run, dict)
        or run.get("name") != WORKFLOW_NAME
        or str(run.get("head_sha") or "").lower() != head_sha
        or run.get("event") != "pull_request"
    ):
        return False
    pull_requests = run.get("pull_requests")
    if not isinstance(pull_requests, list):
        return False
    return any(
        isinstance(candidate, dict)
        and isinstance(candidate.get("number"), int)
        and not isinstance(candidate.get("number"), bool)
        and candidate["number"] == pr_number
        for candidate in pull_requests
    )


def matching_pre_pr_runs(
    runs: list[dict[str, Any]],
    head_sha: str,
    pr_number: int,
) -> list[dict[str, Any]]:
    return [
        run for run in runs
        if run_matches_pull_request(run, head_sha, pr_number)
    ]


def list_pre_pr_runs(
    repository: str,
    head_sha: str,
    pr_number: int,
    token: str,
) -> list[dict[str, Any]]:
    """Busca runs do workflow e contorna respostas filtradas vazias sem relaxar o SHA."""
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number < 1:
        raise AdmissionGuardError("pr_number_invalid")
    workflow = quote(WORKFLOW_FILE, safe="")
    exact_query = urlencode({"head_sha": head_sha, "per_page": 100})
    exact_payload = github_json(
        repository,
        f"actions/workflows/{workflow}/runs?{exact_query}",
        token,
    )
    exact_runs = (
        exact_payload.get("workflow_runs")
        if isinstance(exact_payload.get("workflow_runs"), list)
        else []
    )
    matching = matching_pre_pr_runs(exact_runs, head_sha, pr_number)
    if matching:
        return matching

    # A API do GitHub pode devolver zero (ou uma visão incompleta) quando
    # head_sha é usado com o GITHUB_TOKEN do próprio workflow. O fallback é
    # limitado, permanece no endpoint canônico e volta a impor localmente o
    # nome do workflow e o SHA completo antes de qualquer artifact ser lido.
    runs_by_id: dict[int, dict[str, Any]] = {}
    for page in range(1, WORKFLOW_RUN_FALLBACK_MAX_PAGES + 1):
        fallback_query = urlencode({"per_page": 100, "page": page})
        fallback_payload = github_json(
            repository,
            f"actions/workflows/{workflow}/runs?{fallback_query}",
            token,
        )
        batch = (
            fallback_payload.get("workflow_runs")
            if isinstance(fallback_payload.get("workflow_runs"), list)
            else []
        )
        for run in matching_pre_pr_runs(batch, head_sha, pr_number):
            run_id = int(run.get("id") or 0)
            if run_id > 0:
                runs_by_id[run_id] = run
        matching = list(runs_by_id.values())
        if matching or len(batch) < 100:
            break
    return matching


def matching_artifact(artifacts: list[dict[str, Any]], head_sha: str) -> dict[str, Any] | None:
    expected = f"ci-admission-{head_sha}"
    for artifact in artifacts:
        if (
            isinstance(artifact, dict)
            and artifact.get("name") == expected
            and artifact.get("expired") is not True
        ):
            return artifact
    return None


def evaluate_compare(compare: dict[str, Any], base_sha: str, head_sha: str) -> dict[str, Any]:
    behind_by = int(compare.get("behind_by") or 0)
    status = str(compare.get("status") or "")
    if behind_by > 0 or status not in {"ahead", "identical"}:
        raise AdmissionGuardError(
            f"source_stale_or_diverged:base={base_sha}:head={head_sha}:status={status}:behind_by={behind_by}"
        )
    return {"status": status, "behind_by": behind_by, "ahead_by": int(compare.get("ahead_by") or 0)}


def assert_base_freshness(repository: str, base_ref: str, head_sha: str, token: str) -> dict[str, Any]:
    branch = github_json(repository, f"branches/{quote(base_ref, safe='')}", token)
    commit = branch.get("commit") if isinstance(branch.get("commit"), dict) else {}
    base_sha = str(commit.get("sha") or "").strip().lower()
    if not SHA40.fullmatch(base_sha):
        raise AdmissionGuardError("base_sha_invalid")
    compare = github_json(repository, f"compare/{base_sha}...{head_sha}", token)
    state = evaluate_compare(compare, base_sha, head_sha)
    return {"base_ref": base_ref, "base_sha": base_sha, **state}


def verify_evidence(
    repository: str,
    head_sha: str,
    base_sha: str,
    token: str,
    pr_number: int,
) -> dict[str, Any]:
    matching = list_pre_pr_runs(repository, head_sha, pr_number, token)
    candidates = successful_pre_pr_runs(matching, head_sha, pr_number)
    if not candidates:
        if any(run.get("status") != "completed" for run in matching):
            raise AdmissionGuardError("pre_pr_pending_for_head_sha")
        if any(run.get("status") == "completed" and run.get("conclusion") not in {"success", "neutral", "skipped"} for run in matching):
            raise AdmissionGuardError("pre_pr_failed_for_head_sha")
        raise AdmissionGuardError("pre_pr_success_missing_for_head_sha")

    for run in candidates:
        run_id = int(run.get("id") or 0)
        if run_id < 1:
            continue
        artifacts_payload = github_json(repository, f"actions/runs/{run_id}/artifacts?per_page=100", token)
        artifacts = artifacts_payload.get("artifacts") if isinstance(artifacts_payload.get("artifacts"), list) else []
        artifact = matching_artifact(artifacts, head_sha)
        if artifact:
            manifest = load_and_validate_manifest(repository, artifact, head_sha, base_sha, token)
            return {
                "workflow": WORKFLOW_NAME,
                "pre_pr_run_id": run_id,
                "artifact": {
                    "id": artifact.get("id"),
                    "name": artifact.get("name"),
                    "expired": artifact.get("expired"),
                },
                "manifest": manifest,
            }
    raise AdmissionGuardError("admission_manifest_missing_for_head_sha")


def assert_pr_revision(
    repository: str,
    pr_number: int,
    head_sha: str,
    base_ref: str,
    token: str,
) -> None:
    """Independently read back the PR before accepting a completed Pre-PR receipt."""
    pr = github_json(repository, f"pulls/{pr_number}", token)
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    if (
        pr.get("state") != "open"
        or str(head.get("sha") or "").lower() != head_sha
        or str(base.get("ref") or "") != base_ref
    ):
        raise AdmissionGuardError("pr_revision_changed_while_waiting")


def wait_for_admission(
    repository: str,
    head_sha: str,
    base_ref: str,
    token: str,
    max_wait_seconds: int,
    poll_seconds: int,
    pr_number: int,
) -> dict[str, Any]:
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number < 1:
        raise AdmissionGuardError("pr_number_invalid")
    if not 0 <= max_wait_seconds <= MAX_ADMISSION_WAIT_SECONDS:
        raise AdmissionGuardError("admission_wait_budget_invalid")
    if not 1 <= poll_seconds <= MAX_ADMISSION_POLL_SECONDS:
        raise AdmissionGuardError("admission_poll_interval_invalid")
    freshness = assert_base_freshness(repository, base_ref, head_sha, token)
    deadline = time.monotonic() + max_wait_seconds
    while True:
        try:
            evidence = verify_evidence(
                repository,
                head_sha,
                freshness["base_sha"],
                token,
                pr_number,
            )
            latest_base = assert_base_freshness(repository, base_ref, head_sha, token)
            if latest_base["base_sha"] != freshness["base_sha"]:
                raise AdmissionGuardError("base_changed_while_waiting")
            assert_pr_revision(repository, pr_number, head_sha, base_ref, token)
            return {
                "schema_version": "1.1.0",
                "result": "ADMISSION_ACCEPTED",
                "generated_at_utc": utc_now(),
                "head_sha": head_sha,
                "base": latest_base,
                **evidence,
            }
        except AdmissionGuardError as exc:
            reason = str(exc)
            if reason not in RETRYABLE_REASONS or time.monotonic() >= deadline:
                raise
            time.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida manifesto de admissão antes de CI caro.")
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--head-sha", default=os.getenv("GITHUB_SHA", ""))
    parser.add_argument("--event-name", default=os.getenv("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--base-ref", default="main")
    parser.add_argument("--pr-number", type=int, default=0)
    parser.add_argument("--max-wait-seconds", type=int, default=600)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.event_name != "pull_request":
        result = {
            "schema_version": "1.0.0",
            "result": "ADMISSION_NOT_REQUIRED",
            "generated_at_utc": utc_now(),
            "event_name": args.event_name,
            "head_sha": args.head_sha,
        }
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 0

    sha = args.head_sha.strip().lower()
    if not SHA40.fullmatch(sha):
        blocked = {
            "schema_version": "1.0.0",
            "result": "ADMISSION_BLOCKED",
            "generated_at_utc": utc_now(),
            "head_sha": args.head_sha,
            "reason": "head_sha_invalid",
        }
        args.output.write_text(json.dumps(blocked, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(blocked, sort_keys=True))
        return 1

    try:
        result = wait_for_admission(
            args.repository,
            sha,
            args.base_ref,
            os.getenv("GITHUB_TOKEN", "").strip(),
            args.max_wait_seconds,
            args.poll_seconds,
            args.pr_number,
        )
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 0
    except AdmissionGuardError as exc:
        blocked = {
            "schema_version": "1.0.0",
            "result": "ADMISSION_BLOCKED",
            "generated_at_utc": utc_now(),
            "head_sha": sha,
            "base_ref": args.base_ref,
            "reason": str(exc),
        }
        args.output.write_text(json.dumps(blocked, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(blocked, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
