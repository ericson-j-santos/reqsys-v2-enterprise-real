#!/usr/bin/env python3
"""Ponte efêmera e governada do Noteri para CI do reqsys-powerplatform-alm."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

EXPECTED_HOST = "Noteri"
EXPECTED_LOGIN = "ericson-j-santos"
TARGET_REPOSITORY = "ericson-j-santos/reqsys-powerplatform-alm"
TARGET_REPOSITORY_URL = f"https://github.com/{TARGET_REPOSITORY}"
TARGET_BASE = "main"
TARGET_JOB_LABELS = frozenset({"self-hosted", "Windows", "X64", "noteri", "reqsys-dev"})
RUNNER_VERSION = "2.337.0"
RUNNER_ASSET_URL = (
    "https://github.com/actions/runner/releases/download/"
    f"v{RUNNER_VERSION}/actions-runner-win-x64-{RUNNER_VERSION}.zip"
)
RUNNER_ASSET_SHA256 = "1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc"
RUNNER_LABELS = "noteri,reqsys-dev"
RUNNER_SLOTS = 2
POLL_SECONDS = 10
TIMEOUT_SECONDS = 900


class BridgeError(RuntimeError):
    def __init__(self, state: str, message: str) -> None:
        super().__init__(message)
        self.state = state


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _gh_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return env


def _find_gh() -> Path:
    found = shutil.which("gh")
    candidates = [
        Path(found) if found else None,
        Path(os.environ.get("ProgramFiles") or r"C:\Program Files") / "GitHub CLI" / "gh.exe",
        Path(os.environ.get("LOCALAPPDATA") or "") / "Programs" / "GitHub CLI" / "gh.exe",
    ]
    for item in candidates:
        if item and item.is_file():
            return item
    raise BridgeError("github_cli_missing", "GitHub CLI não encontrado")


def _run_gh(gh: Path, args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(gh), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=_gh_env(),
    )


def _gh_value(gh: Path, endpoint: str) -> Any:
    cp = _run_gh(gh, ["api", endpoint])
    if cp.returncode != 0:
        raise BridgeError(
            "github_api_failed",
            f"GitHub API falhou para endpoint governado: {endpoint.split('?')[0]}",
        )
    try:
        return json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        raise BridgeError("github_api_invalid_json", "GitHub API retornou JSON inválido") from exc


def _gh_json(gh: Path, endpoint: str) -> dict[str, Any]:
    value = _gh_value(gh, endpoint)
    if not isinstance(value, dict):
        raise BridgeError("github_api_invalid_shape", "GitHub API retornou formato inesperado")
    return value


def _gh_list(gh: Path, endpoint: str) -> list[dict[str, Any]]:
    value = _gh_value(gh, endpoint)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise BridgeError("github_api_invalid_shape", "GitHub API retornou lista inesperada")
    return value


def _validate_host() -> str:
    if os.name != "nt":
        raise BridgeError("windows_required", "Windows obrigatório")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise BridgeError("host_mismatch", f"host inesperado: {host}")
    if platform.machine().casefold() not in {"amd64", "x86_64"}:
        raise BridgeError("x64_required", "arquitetura x64 obrigatória")
    return host


def _validate_identity(gh: Path) -> None:
    cp = _run_gh(gh, ["api", "user", "--jq", ".login"])
    if cp.returncode != 0 or cp.stdout.strip().casefold() != EXPECTED_LOGIN.casefold():
        raise BridgeError("github_identity_mismatch", "perfil local gh não pertence ao owner esperado")


def _valid_head_sha(value: Any) -> str:
    sha = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise BridgeError("target_pr_head_invalid", "HEAD atual da PR alvo é inválido")
    return sha


def _workflow_runs(gh: Path, expected_head: str) -> list[dict[str, Any]]:
    payload = _gh_json(
        gh,
        f"repos/{TARGET_REPOSITORY}/actions/runs?head_sha={expected_head}&event=pull_request&per_page=100",
    )
    runs = payload.get("workflow_runs") or []
    if not isinstance(runs, list):
        raise BridgeError("github_api_invalid_shape", "workflow_runs inválido")
    return [item for item in runs if isinstance(item, dict)]


def _workflow_runs_for_branch(gh: Path, branch: str) -> list[dict[str, Any]]:
    payload = _gh_json(
        gh,
        f"repos/{TARGET_REPOSITORY}/actions/runs?branch={quote(branch, safe='')}&event=pull_request&per_page=100",
    )
    runs = payload.get("workflow_runs") or []
    if not isinstance(runs, list):
        raise BridgeError("github_api_invalid_shape", "workflow_runs de branch inválido")
    return [item for item in runs if isinstance(item, dict)]


def _jobs_for_run(gh: Path, run_id: int) -> list[dict[str, Any]]:
    payload = _gh_json(
        gh,
        f"repos/{TARGET_REPOSITORY}/actions/runs/{run_id}/jobs?filter=latest&per_page=100",
    )
    jobs = payload.get("jobs") or []
    if not isinstance(jobs, list):
        raise BridgeError("github_api_invalid_shape", "jobs inválido")
    return [item for item in jobs if isinstance(item, dict)]


def _job_targets_noteri(job: dict[str, Any]) -> bool:
    labels = {str(value) for value in (job.get("labels") or [])}
    return TARGET_JOB_LABELS.issubset(labels)


def _target_job_state(gh: Path, expected_head: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for run in _workflow_runs(gh, expected_head):
        run_id = int(run.get("id") or 0)
        if run_id <= 0:
            continue
        for job in _jobs_for_run(gh, run_id):
            if not _job_targets_noteri(job):
                continue
            selected.append(
                {
                    "id": int(job.get("id") or 0),
                    "run_id": run_id,
                    "workflow": str(run.get("name") or ""),
                    "name": str(job.get("name") or ""),
                    "status": str(job.get("status") or ""),
                    "conclusion": job.get("conclusion"),
                    "runner_id": job.get("runner_id"),
                    "runner_name": job.get("runner_name"),
                    "labels": [str(value) for value in (job.get("labels") or [])],
                }
            )
    return selected


def _pull_request_snapshot(payload: dict[str, Any]) -> dict[str, Any] | None:
    number = int(payload.get("number") or 0)
    if number <= 0 or payload.get("state") != "open":
        return None
    if str((payload.get("base") or {}).get("ref") or "") != TARGET_BASE:
        return None
    head = payload.get("head") or {}
    if str((head.get("repo") or {}).get("full_name") or "") != TARGET_REPOSITORY:
        return None
    branch = str(head.get("ref") or "").strip()
    if not branch:
        return None
    try:
        sha = _valid_head_sha(head.get("sha"))
    except BridgeError:
        return None
    return {
        "number": number,
        "branch": branch,
        "head": sha,
        "draft": bool(payload.get("draft")),
    }


def _select_target_pr(gh: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pulls = _gh_list(
        gh,
        f"repos/{TARGET_REPOSITORY}/pulls?state=open&base={TARGET_BASE}&per_page=100",
    )
    candidates: list[tuple[int, dict[str, Any], list[dict[str, Any]]]] = []
    for payload in pulls:
        snapshot = _pull_request_snapshot(payload)
        if snapshot is None:
            continue
        jobs = _target_job_state(gh, snapshot["head"])
        waiting = [
            job
            for job in jobs
            if job.get("status") == "queued" and not job.get("runner_id")
        ]
        if waiting:
            candidates.append((snapshot["number"], snapshot, jobs))
    if not candidates:
        raise BridgeError(
            "no_eligible_alm_pr",
            "nenhuma PR aberta possui job Noteri aguardando runner no HEAD atual",
        )
    candidates.sort(key=lambda item: item[0])
    _, snapshot, jobs = candidates[0]
    return snapshot, jobs


def _pr_target(gh: Path, target_pr: int, target_branch: str) -> str:
    payload = _gh_json(gh, f"repos/{TARGET_REPOSITORY}/pulls/{target_pr}")
    snapshot = _pull_request_snapshot(payload)
    if snapshot is None:
        raise BridgeError("target_pr_invalid", f"PR #{target_pr} deixou de ser alvo elegível")
    if snapshot["branch"] != target_branch:
        raise BridgeError("target_branch_changed", f"branch da PR #{target_pr} mudou durante a execução")
    return str(snapshot["head"])


def _cancel_stale_runs(
    gh: Path,
    *,
    target_pr: int,
    target_branch: str,
    expected_head: str,
) -> list[int]:
    cancelled: list[int] = []
    active = {"queued", "pending", "in_progress", "waiting", "requested"}
    for run in _workflow_runs_for_branch(gh, target_branch):
        run_id = int(run.get("id") or 0)
        head_sha = str(run.get("head_sha") or "").strip().lower()
        status = str(run.get("status") or "")
        if run_id <= 0 or head_sha == expected_head or status not in active:
            continue
        linked = {
            int(item.get("number") or 0)
            for item in (run.get("pull_requests") or [])
            if isinstance(item, dict)
        }
        if linked and target_pr not in linked:
            continue
        cp = _run_gh(
            gh,
            ["api", "--method", "POST", f"repos/{TARGET_REPOSITORY}/actions/runs/{run_id}/cancel"],
        )
        if cp.returncode != 0:
            raise BridgeError("stale_run_cancel_failed", f"falha ao cancelar run obsoleto {run_id}")
        cancelled.append(run_id)
    return cancelled


def _all_runs_terminal(runs: list[dict[str, Any]]) -> bool:
    return bool(runs) and all(str(run.get("status") or "") == "completed" for run in runs)


def _all_runs_success(runs: list[dict[str, Any]]) -> bool:
    accepted = {"success", "skipped", "neutral"}
    return _all_runs_terminal(runs) and all(str(run.get("conclusion") or "") in accepted for run in runs)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_runner(root: Path) -> Path:
    archive = root / f"actions-runner-{RUNNER_VERSION}.zip"
    request = urllib.request.Request(
        RUNNER_ASSET_URL,
        headers={"User-Agent": "ReqSys-Noteri-ALM-Runner-Bridge/2.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as output:
        shutil.copyfileobj(response, output)
    if _sha256(archive).casefold() != RUNNER_ASSET_SHA256.casefold():
        raise BridgeError("runner_digest_mismatch", "SHA-256 do runner oficial divergiu")
    return archive


def _extract_runner(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=False)
    resolved = target.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            destination = (target / member.filename).resolve()
            if destination != resolved and resolved not in destination.parents:
                raise BridgeError("runner_archive_invalid", "arquivo do runner contém caminho inválido")
        zf.extractall(target)
    required = (target / "config.cmd", target / "bin" / "Runner.Listener.exe")
    if not all(item.is_file() for item in required):
        raise BridgeError("runner_install_incomplete", "binários oficiais do runner incompletos")


def _registration_token(gh: Path) -> str:
    cp = _run_gh(
        gh,
        [
            "api", "--method", "POST",
            f"repos/{TARGET_REPOSITORY}/actions/runners/registration-token",
            "--jq", ".token",
        ],
    )
    token = cp.stdout.strip()
    if cp.returncode != 0 or len(token) < 20:
        raise BridgeError("runner_admin_permission_required", "perfil local gh não autorizou registro do runner")
    return token


def _register_slot(gh: Path, archive: Path, root: Path, slot: int) -> tuple[Path, str]:
    home = root / f"slot-{slot}"
    _extract_runner(archive, home)
    token = _registration_token(gh)
    name = f"Noteri-ALM-{os.environ.get('GITHUB_RUN_ID', 'manual')}-{slot}"
    try:
        cp = subprocess.run(
            [
                str(home / "config.cmd"),
                "--unattended",
                "--url", TARGET_REPOSITORY_URL,
                "--token", token,
                "--name", name,
                "--labels", RUNNER_LABELS,
                "--work", "_work",
                "--ephemeral",
                "--disableupdate",
            ],
            cwd=home,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    finally:
        del token
    if cp.returncode != 0 or not (home / ".runner").is_file():
        raise BridgeError("runner_registration_failed", f"registro do slot {slot} falhou")
    return home, name


def _start_listener(home: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [str(home / "bin" / "Runner.Listener.exe"), "run"],
        cwd=home,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
    )


def _stop_processes(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def _resolve_evidence_path() -> Path:
    raw = (os.environ.get("REQSYS_ALM_RUNNER_EVIDENCE_FILE") or "").strip()
    temp_raw = (os.environ.get("RUNNER_TEMP") or "").strip()
    if not raw or not temp_raw:
        raise BridgeError("evidence_path_missing", "RUNNER_TEMP/evidence path ausente")
    path = Path(raw).resolve()
    temp_root = Path(temp_raw).resolve()
    if path.parent != temp_root or path.suffix.casefold() != ".json":
        raise BridgeError("evidence_path_invalid", "evidência deve permanecer diretamente em RUNNER_TEMP")
    return path


def _write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    evidence: dict[str, Any] = {
        "schema": "reqsys-noteri-alm-runner-bridge/v2",
        "target_repository": TARGET_REPOSITORY,
        "target_base": TARGET_BASE,
        "selection_policy": "lowest_open_pr_with_unassigned_noteri_job",
        "runner_labels": RUNNER_LABELS.split(","),
        "production_touched": False,
        "secrets_read": False,
        "token_exposed": False,
        "registration_token_persisted": False,
        "registration_token_logged": False,
        "independent_readback": False,
        "replay_idempotent": False,
        "pickup_verified": False,
        "runner_slots": RUNNER_SLOTS,
        "stale_runs_cancelled": [],
    }
    processes: list[subprocess.Popen[bytes]] = []
    runtime_root: Path | None = None
    evidence_path: Path | None = None
    try:
        evidence_path = _resolve_evidence_path()
        evidence["host"] = _validate_host()
        gh = _find_gh()
        _validate_identity(gh)

        target, jobs_before = _select_target_pr(gh)
        target_pr = int(target["number"])
        target_branch = str(target["branch"])
        expected_head = str(target["head"])
        evidence["target_pr"] = target_pr
        evidence["target_branch"] = target_branch
        evidence["target_draft"] = bool(target["draft"])
        evidence["expected_head"] = expected_head
        evidence["observed_head_before"] = expected_head
        evidence["target_jobs_before"] = jobs_before

        cancelled = _cancel_stale_runs(
            gh,
            target_pr=target_pr,
            target_branch=target_branch,
            expected_head=expected_head,
        )
        evidence["stale_runs_cancelled"] = cancelled

        if _pr_target(gh, target_pr, target_branch) != expected_head:
            raise BridgeError("target_head_changed_before_registration", "HEAD mudou antes do registro do runner")

        base = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir())
        runtime_root = Path(tempfile.mkdtemp(prefix="reqsys-alm-bridge-", dir=str(base)))
        archive = _download_runner(runtime_root)
        names: list[str] = []
        for slot in range(1, RUNNER_SLOTS + 1):
            home, name = _register_slot(gh, archive, runtime_root, slot)
            names.append(name)
            processes.append(_start_listener(home))
        evidence["runner_names"] = names

        deadline = time.monotonic() + TIMEOUT_SECONDS
        final_jobs = jobs_before
        final_runs = _workflow_runs(gh, expected_head)
        while time.monotonic() < deadline:
            if _pr_target(gh, target_pr, target_branch) != expected_head:
                raise BridgeError("target_head_changed_during_run", f"PR #{target_pr} mudou durante a execução")
            final_jobs = _target_job_state(gh, expected_head)
            final_runs = _workflow_runs(gh, expected_head)
            pickups = [
                job for job in final_jobs
                if job.get("runner_id") and str(job.get("runner_name") or "") in names
            ]
            if pickups and _all_runs_terminal(final_runs):
                break
            time.sleep(POLL_SECONDS)

        after = _pr_target(gh, target_pr, target_branch)
        final_jobs = _target_job_state(gh, expected_head)
        final_runs = _workflow_runs(gh, expected_head)
        pickups = [
            job for job in final_jobs
            if job.get("runner_id") and str(job.get("runner_name") or "") in names
        ]
        evidence["observed_head_after"] = after
        evidence["target_jobs_after"] = final_jobs
        evidence["workflow_runs_after"] = [
            {
                "id": int(run.get("id") or 0),
                "name": str(run.get("name") or ""),
                "status": str(run.get("status") or ""),
                "conclusion": run.get("conclusion"),
                "head_sha": str(run.get("head_sha") or "").lower(),
            }
            for run in final_runs
        ]
        evidence["pickup_jobs"] = pickups
        evidence["pickup_verified"] = bool(pickups)
        evidence["target_runs_terminal"] = _all_runs_terminal(final_runs)
        evidence["target_runs_success"] = _all_runs_success(final_runs)
        evidence["independent_readback"] = (
            after == expected_head
            and bool(pickups)
            and _all_runs_terminal(final_runs)
        )
        evidence["replay_idempotent"] = (
            evidence["independent_readback"]
            and not any(
                job.get("status") == "queued" and not job.get("runner_id")
                for job in final_jobs
            )
        )

        if after != expected_head:
            raise BridgeError("target_head_changed_after_run", f"PR #{target_pr} mudou antes do readback final")
        if not evidence["pickup_verified"]:
            raise BridgeError("runner_pickup_timeout", "nenhum job do HEAD atual comprovou pickup nos runners efêmeros")
        if not evidence["target_runs_terminal"]:
            raise BridgeError("target_checks_timeout", "runs do HEAD atual não chegaram a estado terminal")

        evidence["status"] = "PICKUP_VERIFIED"
        _write_evidence(evidence_path, evidence)
        _emit(
            {
                "ok": True,
                "status": "PICKUP_VERIFIED",
                "target_pr": target_pr,
                "target_runs_success": evidence["target_runs_success"],
            }
        )
        return 0
    except BridgeError as exc:
        evidence["status"] = "BLOCKED"
        evidence["reason"] = exc.state
        evidence["error"] = str(exc)[:500]
        if evidence_path is not None:
            _write_evidence(evidence_path, evidence)
        _emit({"ok": False, "status": "BLOCKED", "reason": exc.state})
        return 5
    except Exception as exc:
        evidence["status"] = "BLOCKED"
        evidence["reason"] = "unexpected_error"
        evidence["error_type"] = type(exc).__name__
        evidence["error"] = str(exc)[:500]
        if evidence_path is not None:
            _write_evidence(evidence_path, evidence)
        _emit({"ok": False, "status": "BLOCKED", "reason": "unexpected_error"})
        return 2
    finally:
        _stop_processes(processes)
        if runtime_root and runtime_root.exists():
            shutil.rmtree(runtime_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
