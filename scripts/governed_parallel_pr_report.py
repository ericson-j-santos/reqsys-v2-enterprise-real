#!/usr/bin/env python3
"""Relatório de capacidade paralela segura para Merge Queue Governada.

Read-only: classifica PRs abertos, detecta conflitos de paths entre elegíveis
e estima quantos merges paralelos são seguros sem elevar risco operacional.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SCHEMA_VERSION = "1.0.0"
ELIGIBLE_LABEL = "merge-queue:eligible"
STANDARD_PARALLEL_PRS = 3

HIGH_RISK_RE = re.compile(
    r"(^|/)(auth|security|secrets|jwt|cors|deploy|fly|docker|Dockerfile|\.github/workflows/)",
    re.IGNORECASE,
)
LOW_RISK_MARKERS = (
    "docs/",
    "runbooks/",
    "artifacts/",
    "tests/",
    "test/",
    "__tests__/",
    "observability",
    "analytics",
    "dashboard",
    "evidence",
    "release note",
)


@dataclass(frozen=True)
class PullRequestSnapshot:
    number: int
    title: str
    url: str
    draft: bool
    base_ref: str
    head_sha: str
    labels: tuple[str, ...]
    files: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return ELIGIBLE_LABEL in self.labels and not self.draft


def github_request(method: str, url: str, token: str) -> Any:
    request = Request(
        url,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {method} {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API connection error for {method} {url}: {exc}") from exc


def api_url(repo: str, path: str, **params: str | int) -> str:
    url = f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"
    if params:
        return f"{url}?{urlencode(params)}"
    return url


def classify_domain(files: list[str]) -> str:
    if not files:
        return "controlled"
    if any(HIGH_RISK_RE.search(path) for path in files):
        return "high_risk"
    normalized = [path.lower() for path in files]
    if all(any(marker in path for marker in LOW_RISK_MARKERS) for path in normalized):
        return "low_risk"
    return "controlled"


def connected_components(pr_numbers: list[int], edges: list[tuple[int, int]]) -> list[list[int]]:
    parent = {number: number for number in pr_numbers}

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left, right in edges:
        union(left, right)

    groups: dict[int, list[int]] = defaultdict(list)
    for number in pr_numbers:
        groups[find(number)].append(number)
    return [sorted(group) for group in groups.values()]


def find_path_conflicts(prs: list[PullRequestSnapshot]) -> list[dict[str, Any]]:
    file_to_prs: dict[str, list[int]] = defaultdict(list)
    for pr in prs:
        for path in pr.files:
            file_to_prs[path].append(pr.number)

    edges: list[tuple[int, int]] = []
    conflicts: list[dict[str, Any]] = []
    seen_pairs: set[tuple[int, int]] = set()

    for path, numbers in sorted(file_to_prs.items()):
        unique = sorted(set(numbers))
        if len(unique) < 2:
            continue
        conflicts.append({"path": path, "prs": unique})
        for index, left in enumerate(unique):
            for right in unique[index + 1 :]:
                pair = (left, right)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    edges.append(pair)

    return conflicts


def compute_safe_parallel_capacity(
    eligible_prs: list[PullRequestSnapshot],
    *,
    standard_parallel_prs: int = STANDARD_PARALLEL_PRS,
) -> dict[str, Any]:
    eligible_numbers = [pr.number for pr in eligible_prs]
    conflicts = find_path_conflicts(eligible_prs)
    edges = []
    seen_pairs: set[tuple[int, int]] = set()
    for item in conflicts:
        numbers = item["prs"]
        for index, left in enumerate(numbers):
            for right in numbers[index + 1 :]:
                pair = (left, right)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    edges.append(pair)

    components = connected_components(eligible_numbers, edges) if eligible_numbers else []
    overlap_penalty = sum(len(component) - 1 for component in components if len(component) > 1)
    low_risk_eligible = sum(1 for pr in eligible_prs if classify_domain(list(pr.files)) == "low_risk")
    raw_capacity = max(0, min(standard_parallel_prs, len(eligible_prs) - overlap_penalty))
    low_risk_capacity = max(0, min(standard_parallel_prs, low_risk_eligible - overlap_penalty))

    if len(eligible_prs) == 0:
        decision = "no_eligible_prs"
    elif raw_capacity == 0:
        decision = "block_parallel_merges"
    elif raw_capacity < standard_parallel_prs:
        decision = "limit_parallel_merges"
    else:
        decision = "parallel_capacity_available"

    return {
        "standard_parallel_prs": standard_parallel_prs,
        "eligible_prs": len(eligible_prs),
        "low_risk_eligible_prs": low_risk_eligible,
        "overlap_penalty": overlap_penalty,
        "safe_parallel_capacity": raw_capacity,
        "low_risk_parallel_capacity": low_risk_capacity,
        "decision": decision,
        "conflict_components": components,
        "path_conflicts": conflicts,
    }


def build_parallel_capacity_report(
    prs: list[PullRequestSnapshot],
    *,
    repo: str,
    correlation_id: str,
    allow_auto_merge: bool = False,
    standard_parallel_prs: int = STANDARD_PARALLEL_PRS,
) -> dict[str, Any]:
    eligible = [pr for pr in prs if pr.eligible]
    capacity = compute_safe_parallel_capacity(eligible, standard_parallel_prs=standard_parallel_prs)

    domain_buckets: dict[str, list[dict[str, Any]]] = {
        "low_risk": [],
        "controlled": [],
        "high_risk": [],
    }
    for pr in prs:
        domain = classify_domain(list(pr.files))
        domain_buckets[domain].append(
            {
                "number": pr.number,
                "title": pr.title,
                "eligible": pr.eligible,
                "draft": pr.draft,
                "labels": list(pr.labels),
                "file_count": len(pr.files),
            }
        )

    recommended_actions: list[str] = []
    if capacity["decision"] == "no_eligible_prs":
        recommended_actions.append("Aguardar Governed Merge Queue marcar PRs com merge-queue:eligible.")
    elif capacity["decision"] == "block_parallel_merges":
        recommended_actions.append("Resolver conflitos de paths entre PRs elegíveis antes de merge paralelo.")
    elif capacity["decision"] == "limit_parallel_merges":
        recommended_actions.append(
            f"Limitar merges simultâneos a {capacity['safe_parallel_capacity']} PR(s) com menor sobreposição de paths."
        )
    else:
        recommended_actions.append(
            f"Capacidade paralela segura disponível até {capacity['safe_parallel_capacity']} PR(s)."
        )

    if allow_auto_merge:
        recommended_actions.append(
            "allow_auto_merge=true: habilitar auto-merge nativo por PR após demais gates obrigatórios."
        )
    else:
        recommended_actions.append(
            "allow_auto_merge=false: usar Governed PR Automation com execute_merge=true por PR elegível."
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "governed_parallel_pr_report",
        "status": capacity["decision"],
        "mode": "report_only",
        "correlation_id": correlation_id,
        "repository": repo,
        "allow_auto_merge": allow_auto_merge,
        "open_prs": len(prs),
        "eligible_prs": capacity["eligible_prs"],
        "safe_parallel_capacity": capacity["safe_parallel_capacity"],
        "low_risk_parallel_capacity": capacity["low_risk_parallel_capacity"],
        "standard_parallel_prs": capacity["standard_parallel_prs"],
        "decision": capacity["decision"],
        "domain_buckets": domain_buckets,
        "path_conflicts": capacity["path_conflicts"],
        "conflict_components": capacity["conflict_components"],
        "prs": [
            {
                "number": pr.number,
                "title": pr.title,
                "url": pr.url,
                "draft": pr.draft,
                "eligible": pr.eligible,
                "domain": classify_domain(list(pr.files)),
                "labels": list(pr.labels),
                "files": list(pr.files),
            }
            for pr in prs
        ],
        "recommended_actions": recommended_actions,
        "guardrails": {
            "merge": False,
            "deploy": False,
            "auto_merge_execute": False,
        },
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "parallel-capacity-report.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Governed Parallel PR Capacity Report",
        "",
        f"- Repository: `{report['repository']}`",
        f"- Generated at: `{report['generated_at']}`",
        f"- Decision: `{report['decision']}`",
        f"- Open PRs: `{report['open_prs']}`",
        f"- Eligible PRs: `{report['eligible_prs']}`",
        f"- Safe parallel capacity: `{report['safe_parallel_capacity']}`",
        f"- allow_auto_merge: `{report['allow_auto_merge']}`",
        "",
        "## Recommended actions",
        "",
    ]
    lines.extend(f"- {action}" for action in report["recommended_actions"])
    lines.extend(["", "## Path conflicts", ""])
    if report["path_conflicts"]:
        for conflict in report["path_conflicts"]:
            prs = ", ".join(f"#{number}" for number in conflict["prs"])
            lines.append(f"- `{conflict['path']}` → {prs}")
    else:
        lines.append("- Nenhum conflito de path entre PRs elegíveis.")

    (output_dir / "parallel-capacity-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def list_pr_labels(repo: str, token: str, number: int) -> list[str]:
    payload = github_request("GET", api_url(repo, f"issues/{number}/labels", per_page=100), token)
    return [item.get("name", "") for item in payload if item.get("name")]


def list_pr_files(repo: str, token: str, number: int) -> list[str]:
    payload = github_request("GET", api_url(repo, f"pulls/{number}/files", per_page=100), token)
    return [item.get("filename", "") for item in payload if item.get("filename")]


def fetch_open_pr_snapshots(repo: str, token: str, limit: int) -> list[PullRequestSnapshot]:
    payload = github_request("GET", api_url(repo, "pulls", state="open", per_page=limit, sort="updated", direction="desc"), token)
    snapshots: list[PullRequestSnapshot] = []
    for item in payload:
        number = int(item["number"])
        snapshots.append(
            PullRequestSnapshot(
                number=number,
                title=item.get("title") or "",
                url=item.get("html_url") or "",
                draft=bool(item.get("draft")),
                base_ref=item.get("base", {}).get("ref") or "main",
                head_sha=item.get("head", {}).get("sha") or "",
                labels=tuple(list_pr_labels(repo, token, number)),
                files=tuple(list_pr_files(repo, token, number)),
            )
        )
    return snapshots


def fetch_allow_auto_merge(repo: str, token: str) -> bool:
    payload = github_request("GET", api_url(repo, ""), token)
    return bool(payload.get("allow_auto_merge"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Governed parallel PR capacity report.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--output-dir", default="artifacts/governed-merge-queue")
    parser.add_argument("--pr-limit", type=int, default=30)
    parser.add_argument("--standard-parallel-prs", type=int, default=STANDARD_PARALLEL_PRS)
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--input-json", help="Optional local JSON fixture with PR snapshots for offline mode.")
    parser.add_argument("--allow-auto-merge", choices=("true", "false", "auto"), default="auto")
    return parser.parse_args()


def snapshots_from_fixture(data: list[dict[str, Any]]) -> list[PullRequestSnapshot]:
    snapshots: list[PullRequestSnapshot] = []
    for item in data:
        snapshots.append(
            PullRequestSnapshot(
                number=int(item["number"]),
                title=item.get("title", ""),
                url=item.get("url", ""),
                draft=bool(item.get("draft", False)),
                base_ref=item.get("base_ref", "main"),
                head_sha=item.get("head_sha", ""),
                labels=tuple(item.get("labels", [])),
                files=tuple(item.get("files", [])),
            )
        )
    return snapshots


def main() -> int:
    args = parse_args()
    if not args.repo and not args.input_json:
        print("GITHUB_REPOSITORY or --repo is required", file=sys.stderr)
        return 1

    correlation_id = args.correlation_id or f"governed-parallel-pr-report-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    if args.input_json:
        fixture = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
        snapshots = snapshots_from_fixture(fixture)
        allow_auto_merge = args.allow_auto_merge == "true"
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            print("GITHUB_TOKEN is required", file=sys.stderr)
            return 1
        snapshots = fetch_open_pr_snapshots(args.repo, token, args.pr_limit)
        if args.allow_auto_merge == "auto":
            allow_auto_merge = fetch_allow_auto_merge(args.repo, token)
        else:
            allow_auto_merge = args.allow_auto_merge == "true"

    report = build_parallel_capacity_report(
        snapshots,
        repo=args.repo or "local-fixture",
        correlation_id=correlation_id,
        allow_auto_merge=allow_auto_merge,
        standard_parallel_prs=args.standard_parallel_prs,
    )
    write_report(report, Path(args.output_dir))
    print(json.dumps({"decision": report["decision"], "safe_parallel_capacity": report["safe_parallel_capacity"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
