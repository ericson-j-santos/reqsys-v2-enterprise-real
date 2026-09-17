#!/usr/bin/env python3
"""Coleta Teams/GitLab no runner e grava snapshot normalizado sem segredos."""
from __future__ import annotations

import argparse
import html
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
GITLAB_ROOT = "https://gitlab.com/api/v4"
DEFAULT_GITLAB_PROJECT_ID = "84366761"
TAG_RE = re.compile(r"<[^>]+>")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def required_env(name: str) -> str:
    value = str(os.environ.get(name, "")).strip()
    if not value:
        raise RuntimeError(f"config_missing:{name}")
    return value


def clean_title(value: str, fallback: str) -> str:
    text = TAG_RE.sub(" ", html.unescape(value or ""))
    text = " ".join(text.split())
    return (text or fallback)[:180]


def request_json(url: str, headers: dict[str, str]) -> object:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read(1024 * 1024)
            return json.loads(raw.decode("utf-8")) if raw else {}
    except HTTPError as exc:
        raise RuntimeError(f"source_http_{exc.code}") from None


def fetch_teams(limit: int) -> list[dict]:
    token = required_env("POWER_PLATFORM_GRAPH_ACCESS_TOKEN")
    team = quote(required_env("PLANNER_TEAMS_DEV_TEAM_ID"), safe="")
    channel = quote(required_env("PLANNER_TEAMS_DEV_CHANNEL_ID"), safe="")
    payload = request_json(
        f"{GRAPH_ROOT}/teams/{team}/channels/{channel}/messages?$top={limit}",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if not isinstance(payload, dict):
        raise RuntimeError("teams_payload_invalid")
    return list(payload.get("value") or [])


def fetch_gitlab(limit: int) -> list[dict]:
    token = required_env("GITLAB_MIRROR_TOKEN")
    project_id = quote(str(os.environ.get("GITLAB_PROJECT_ID", DEFAULT_GITLAB_PROJECT_ID)), safe="")
    payload = request_json(
        f"{GITLAB_ROOT}/projects/{project_id}/repository/commits?per_page={limit}",
        {"PRIVATE-TOKEN": token, "Accept": "application/json"},
    )
    if not isinstance(payload, list):
        raise RuntimeError("gitlab_payload_invalid")
    return payload


def normalize_teams(item: dict) -> dict:
    message_id = str(item.get("id") or "").strip()
    if not message_id:
        raise ValueError("teams_message_id_missing")
    body = item.get("body") if isinstance(item.get("body"), dict) else {}
    return {
        "source": "teams",
        "external_id": f"message-{message_id}",
        "title": clean_title(str(body.get("content") or ""), f"Teams message {message_id}"),
        "occurred_at": item.get("createdDateTime") or now_iso(),
        "status": "PENDENTE",
        "priority": "P1",
    }


def normalize_gitlab(item: dict) -> dict:
    commit_id = str(item.get("id") or "").strip()
    if not commit_id:
        raise ValueError("gitlab_commit_id_missing")
    return {
        "source": "gitlab",
        "external_id": f"commit-{commit_id}",
        "title": clean_title(str(item.get("title") or ""), f"GitLab commit {commit_id[:12]}"),
        "occurred_at": item.get("committed_date") or item.get("created_at") or now_iso(),
        "status": "PENDENTE",
        "priority": "P1",
    }


def build_snapshot(teams: list[dict], gitlab: list[dict], generated_at: str | None = None) -> dict:
    items = [normalize_teams(item) for item in teams] + [normalize_gitlab(item) for item in gitlab]
    unique: dict[str, dict] = {}
    for item in items:
        unique[f"{item['source']}:{item['external_id']}"] = item
    ordered = sorted(unique.values(), key=lambda item: str(item.get("occurred_at") or ""), reverse=True)
    return {
        "contract": "todo-event-relay-snapshot-v1",
        "generated_at": generated_at or now_iso(),
        "source_counts": {"teams": len(teams), "gitlab": len(gitlab)},
        "items": ordered,
        "secret_values_persisted": False,
    }


def write_snapshot(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot governado Teams/GitLab para TODO Global")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--teams-limit", type=int, default=50)
    parser.add_argument("--gitlab-limit", type=int, default=20)
    args = parser.parse_args(argv)
    if not 1 <= args.teams_limit <= 50 or not 1 <= args.gitlab_limit <= 100:
        raise SystemExit("limits_out_of_range")
    snapshot = build_snapshot(fetch_teams(args.teams_limit), fetch_gitlab(args.gitlab_limit))
    write_snapshot(args.output, snapshot)
    print(json.dumps({
        "contract": snapshot["contract"],
        "teams": snapshot["source_counts"]["teams"],
        "gitlab": snapshot["source_counts"]["gitlab"],
        "items": len(snapshot["items"]),
        "secret_values_persisted": False,
        "ready": True,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
