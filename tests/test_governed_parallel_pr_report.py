from pathlib import Path
import json
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.governed_parallel_pr_report import (  # noqa: E402
    PullRequestSnapshot,
    build_parallel_capacity_report,
    classify_domain,
    compute_safe_parallel_capacity,
    find_path_conflicts,
)


def pr(number: int, files: list[str], *, eligible: bool = True, draft: bool = False) -> PullRequestSnapshot:
    labels = ("merge-queue:eligible",) if eligible and not draft else ()
    return PullRequestSnapshot(
        number=number,
        title=f"PR {number}",
        url=f"https://example.local/pull/{number}",
        draft=draft,
        base_ref="main",
        head_sha=f"sha-{number}",
        labels=labels,
        files=tuple(files),
    )


def test_classify_domain_low_risk_docs_only() -> None:
    assert classify_domain(["docs/runbooks/governed-merge-queue.md"]) == "low_risk"


def test_classify_domain_high_risk_auth() -> None:
    assert classify_domain(["backend/app/auth/login.py"]) == "high_risk"


def test_find_path_conflicts_detects_shared_files() -> None:
    conflicts = find_path_conflicts([pr(1, ["docs/a.md"]), pr(2, ["docs/a.md", "docs/b.md"])])

    assert len(conflicts) == 1
    assert conflicts[0]["path"] == "docs/a.md"
    assert conflicts[0]["prs"] == [1, 2]


def test_compute_safe_parallel_capacity_without_conflicts() -> None:
    capacity = compute_safe_parallel_capacity([pr(1, ["docs/a.md"]), pr(2, ["tests/b.py"])])

    assert capacity["safe_parallel_capacity"] == 2
    assert capacity["decision"] == "limit_parallel_merges"


def test_compute_safe_parallel_capacity_at_standard_limit() -> None:
    capacity = compute_safe_parallel_capacity(
        [
            pr(1, ["docs/a.md"]),
            pr(2, ["docs/b.md"]),
            pr(3, ["tests/c.py"]),
        ]
    )

    assert capacity["safe_parallel_capacity"] == 3
    assert capacity["decision"] == "parallel_capacity_available"


def test_compute_safe_parallel_capacity_reduces_on_overlap() -> None:
    capacity = compute_safe_parallel_capacity(
        [pr(1, ["frontend/src/router.js"]), pr(2, ["frontend/src/router.js"]), pr(3, ["docs/c.md"])]
    )

    assert capacity["safe_parallel_capacity"] == 2
    assert capacity["decision"] == "limit_parallel_merges"
    assert capacity["overlap_penalty"] == 1


def test_build_parallel_capacity_report_fixture() -> None:
    report = build_parallel_capacity_report(
        [
            pr(10, ["docs/a.md"]),
            pr(11, ["docs/a.md"]),
            pr(12, ["tests/unit/test_x.py"], eligible=False),
        ],
        repo="example/repo",
        correlation_id="test-correlation",
        allow_auto_merge=False,
    )

    assert report["open_prs"] == 3
    assert report["eligible_prs"] == 2
    assert report["allow_auto_merge"] is False
    assert report["decision"] == "limit_parallel_merges"
    assert any("Governed PR Automation" in action for action in report["recommended_actions"])


def test_build_parallel_capacity_report_serializes_json() -> None:
    report = build_parallel_capacity_report([], repo="example/repo", correlation_id="empty")
    payload = json.loads(json.dumps(report))

    assert payload["eligible_prs"] == 0
    assert payload["decision"] == "no_eligible_prs"
