#!/usr/bin/env python3
"""Gera a projeção ao vivo do painel central do ReqSys a partir de fontes oficiais."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

DEFAULT_API_URL = "https://api.github.com"
DEFAULT_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
RUNTIME_WORKFLOWS = (
    "main-post-merge-validation.yml",
    "noteri-study-mode-dev-reconcile.yml",
    "todo-global-hourly-cycle.yml",
    "pc24x7-teams-ephemeral-e2e.yml",
)


class RequestClient(Protocol):
    def request(self, path: str) -> Any: ...


class GitHubAPIError(RuntimeError):
    def __init__(self, status: int | None, reason: str) -> None:
        self.status = status
        self.reason = reason
        super().__init__(f"github_api_error:{status or 'network'}:{reason}")


class GitHubClient:
    def __init__(self, token: str = "", api_url: str = DEFAULT_API_URL, timeout: float = 20.0) -> None:
        self.token = token.strip()
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

    def request(self, path: str) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "reqsys-live-cycle-dashboard/2.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = Request(self.api_url + path, headers=headers)
        try:
            with urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except HTTPError as exc:
            raise GitHubAPIError(exc.code, exc.reason or "http_error") from exc
        except URLError as exc:
            raise GitHubAPIError(None, type(exc.reason).__name__) from exc


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_request(client: RequestClient, path: str) -> tuple[Any | None, str | None]:
    try:
        return client.request(path), None
    except GitHubAPIError as exc:
        return None, f"http_{exc.status}" if exc.status else f"network_{exc.reason}"
    except Exception as exc:  # fail closed without exposing arbitrary response bodies
        return None, f"unexpected_{type(exc).__name__}"


def _latest_run(payload: Any) -> dict[str, Any] | None:
    runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
    if not isinstance(runs, list) or not runs:
        return None
    run = runs[0] if isinstance(runs[0], dict) else None
    if run is None:
        return None
    return {
        "id": run.get("id"),
        "name": run.get("name"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "event": run.get("event"),
        "head_sha": run.get("head_sha"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "url": run.get("html_url"),
    }


def repository_snapshot(client: RequestClient, spec: dict[str, Any]) -> dict[str, Any]:
    repository = str(spec["repository"])
    base = {
        "repository": repository,
        "label": str(spec.get("label") or repository),
        "group": str(spec.get("group") or "outros"),
        "priority": str(spec.get("priority") or "P2"),
    }

    meta, error = _safe_request(client, f"/repos/{repository}")
    if error or not isinstance(meta, dict):
        return {**base, "source_status": "unavailable", "error": error or "invalid_repository_payload"}

    branch = str(meta.get("default_branch") or "main")
    commit, commit_error = _safe_request(
        client,
        f"/repos/{repository}/commits/{quote(branch, safe='')}",
    )
    pulls_query = urlencode({"state": "open", "per_page": "100"})
    pulls, pulls_error = _safe_request(client, f"/repos/{repository}/pulls?{pulls_query}")
    runs_query = urlencode({"branch": branch, "per_page": "20"})
    runs, runs_error = _safe_request(client, f"/repos/{repository}/actions/runs?{runs_query}")

    open_prs: list[dict[str, Any]] = []
    if isinstance(pulls, list):
        for item in pulls[:20]:
            if not isinstance(item, dict):
                continue
            open_prs.append(
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "draft": bool(item.get("draft")),
                    "updated_at": item.get("updated_at"),
                    "head_sha": (item.get("head") or {}).get("sha")
                    if isinstance(item.get("head"), dict)
                    else None,
                    "url": item.get("html_url"),
                }
            )

    sha = commit.get("sha") if isinstance(commit, dict) else None
    commit_url = commit.get("html_url") if isinstance(commit, dict) else None
    commit_date = None
    if isinstance(commit, dict):
        commit_meta = commit.get("commit")
        if isinstance(commit_meta, dict):
            committer = commit_meta.get("committer")
            if isinstance(committer, dict):
                commit_date = committer.get("date")

    errors = [value for value in (commit_error, pulls_error, runs_error) if value]
    visibility = str(meta.get("visibility") or "")
    source_status = "available" if not errors else "partial"
    if visibility == "private":
        latest = _latest_run(runs)
        return {
            **base,
            "repository": None,
            "source_status": source_status,
            "visibility": "private",
            "private_redacted": True,
            "open_pr_count": len(open_prs) if isinstance(pulls, list) else None,
            "latest_ci": (
                {
                    "status": latest.get("status"),
                    "conclusion": latest.get("conclusion"),
                    "updated_at": latest.get("updated_at"),
                }
                if latest
                else None
            ),
            "errors": errors,
        }

    return {
        **base,
        "source_status": source_status,
        "html_url": meta.get("html_url"),
        "visibility": visibility,
        "default_branch": branch,
        "main_sha": sha,
        "main_commit_url": commit_url,
        "main_commit_at": commit_date,
        "updated_at": meta.get("updated_at"),
        "pushed_at": meta.get("pushed_at"),
        "open_pr_count": len(open_prs) if isinstance(pulls, list) else None,
        "open_prs": open_prs,
        "latest_ci": _latest_run(runs),
        "errors": errors,
    }


def workflow_snapshot(
    client: RequestClient,
    repository: str,
    workflow: str,
    *,
    branch: str = "main",
) -> dict[str, Any]:
    query = urlencode({"branch": branch, "per_page": "5"})
    payload, error = _safe_request(
        client,
        f"/repos/{repository}/actions/workflows/{workflow}/runs?{query}",
    )
    return {
        "workflow": workflow,
        "source_status": "available" if error is None else "unavailable",
        "latest_run": _latest_run(payload),
        "error": error,
    }


def load_projects(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    repositories = payload.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise ValueError("projects_config_without_repositories")
    normalized: list[dict[str, Any]] = []
    for item in repositories:
        if not isinstance(item, dict) or not str(item.get("repository") or "").strip():
            raise ValueError("projects_config_invalid_repository")
        normalized.append(item)
    return normalized


def load_optional_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def build_state(
    client: RequestClient,
    *,
    projects: list[dict[str, Any]],
    teams_certification: dict[str, Any] | None,
    repository: str,
    source_sha: str,
    run_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    snapshots = [repository_snapshot(client, spec) for spec in projects]
    current = next(
        (item for item in snapshots if item["repository"] == repository),
        {
            "repository": repository,
            "source_status": "unavailable",
            "open_pr_count": None,
            "open_prs": [],
            "main_sha": None,
            "latest_ci": None,
        },
    )
    if current.get("source_status") == "unavailable":
        raise RuntimeError("current_repository_source_unavailable")

    available = sum(item.get("source_status") in {"available", "partial"} for item in snapshots)
    unavailable = len(snapshots) - available

    todo_global = workflow_snapshot(client, repository, "todo-global-hourly-cycle.yml")
    runtime = [workflow_snapshot(client, repository, name) for name in RUNTIME_WORKFLOWS]

    teams = {
        "source_status": "available" if teams_certification else "unavailable",
        "certification": teams_certification,
        "note": (
            "A certificação é uma projeção operacional do Microsoft Teams; "
            "entrega real só é válida quando a evidência de runtime correspondente existe."
        ),
    }

    return {
        "schema_version": "2.0.0",
        "mode": "live",
        "generated_at": generated_at or utc_now(),
        "source": {
            "repository": repository,
            "sha": source_sha,
            "run_id": run_id,
            "run_url": (
                f"https://github.com/{repository}/actions/runs/{run_id}"
                if run_id and run_id != "local"
                else None
            ),
        },
        "coverage": {
            "total_projects": len(snapshots),
            "available_projects": available,
            "unavailable_projects": unavailable,
            "percent": round((available / len(snapshots)) * 100.0, 2) if snapshots else 0.0,
        },
        "reqsys": {
            "main_sha": current.get("main_sha"),
            "main_commit_url": current.get("main_commit_url"),
            "open_pr_count": current.get("open_pr_count"),
            "open_prs": current.get("open_prs", []),
            "latest_ci": current.get("latest_ci"),
        },
        "todo_global": {
            "source_role": "projection_health",
            "canonical_source": "TODO Global",
            "workflow": todo_global,
            "note": (
                "Este painel não substitui o TODO Global. Ele mostra apenas a saúde da "
                "reconciliação/projeção; estados de TODO continuam pertencendo à fonte canônica."
            ),
        },
        "teams": teams,
        "runtime_pc24x7": {
            "source_role": "workflow_evidence",
            "workflows": runtime,
            "note": "Sucesso de workflow não substitui evidência física same-SHA quando exigida.",
        },
        "projects": snapshots,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera o estado vivo do painel central ReqSys.")
    parser.add_argument("--projects", type=Path, required=True)
    parser.add_argument("--teams-certification", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", DEFAULT_REPOSITORY))
    parser.add_argument("--source-sha", default=os.getenv("GITHUB_SHA", "local"))
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "local"))
    parser.add_argument("--token-env", default="DASHBOARD_GH_TOKEN")
    parser.add_argument("--api-url", default=os.getenv("GITHUB_API_URL", DEFAULT_API_URL))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv(args.token_env, "")
    client = GitHubClient(token=token, api_url=args.api_url)
    state = build_state(
        client,
        projects=load_projects(args.projects),
        teams_certification=load_optional_json(args.teams_certification),
        repository=args.repository,
        source_sha=args.source_sha,
        run_id=args.run_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "generated",
                "output": str(args.output),
                "coverage": state["coverage"],
                "source_sha": state["source"]["sha"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
