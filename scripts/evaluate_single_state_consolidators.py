#!/usr/bin/env python3
"""Validate integrity and consistency of ReqSys single-state consolidator artifacts."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

DEFAULT_VALIDATOR = (
    "artifacts/post-merge-main-runtime-validator/"
    "post-merge-main-runtime-validator.json"
)
DEFAULT_SNAPSHOT = (
    "artifacts/main-operational-state-snapshot/"
    "main-operational-state-snapshot.json"
)
DEFAULT_OUTPUT = (
    "artifacts/single-state-consolidators-integrity/"
    "single-state-consolidators-integrity.json"
)


def load_json_object(path: str | Path) -> tuple[dict[str, Any], str | None]:
    file_path = Path(path)
    if not file_path.exists():
        return {}, f"artifact_missing:{file_path}"
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"artifact_invalid_json:{file_path}:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return {}, f"artifact_not_object:{file_path}"
    return payload, None


def _epoch(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        epoch = int(value)
    except (TypeError, ValueError):
        return None
    return epoch if epoch > 0 else None


def _check(check_id: str, ok: bool, detail: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "detail": detail,
    }


def evaluate_consolidators(
    validator: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    validator_error: str | None = None,
    snapshot_error: str | None = None,
    observed_at_epoch: int | None = None,
    max_clock_skew_seconds: int = 300,
) -> dict[str, Any]:
    if max_clock_skew_seconds < 0:
        raise ValueError("max_clock_skew_seconds must be non-negative")

    now = int(observed_at_epoch if observed_at_epoch is not None else time.time())
    checks: list[dict[str, Any]] = []

    checks.append(
        _check(
            "validator_json_integrity",
            validator_error is None and bool(validator),
            validator_error or "validator JSON object loaded",
        )
    )
    checks.append(
        _check(
            "snapshot_json_integrity",
            snapshot_error is None and bool(snapshot),
            snapshot_error or "snapshot JSON object loaded",
        )
    )

    validator_contract = str(validator.get("contract") or "")
    snapshot_contract = str(snapshot.get("contract") or "")
    checks.append(
        _check(
            "artifact_contracts",
            validator_contract == "post-merge-main-runtime-validator"
            and snapshot_contract == "main-operational-state-snapshot",
            f"validator={validator_contract or 'missing'} "
            f"snapshot={snapshot_contract or 'missing'}",
        )
    )

    validator_sha = str(validator.get("sha") or "").strip()
    snapshot_sha = str(snapshot.get("sha") or "").strip()
    validator_repo = str(validator.get("repo") or "").strip()
    snapshot_repo = str(snapshot.get("repo") or "").strip()
    validator_run = str(validator.get("github_run_id") or "").strip()
    snapshot_run = str(snapshot.get("github_run_id") or "").strip()

    checks.append(
        _check(
            "sha_consistency",
            bool(validator_sha) and validator_sha == snapshot_sha,
            f"validator={validator_sha or 'missing'} "
            f"snapshot={snapshot_sha or 'missing'}",
        )
    )
    checks.append(
        _check(
            "repository_consistency",
            bool(validator_repo) and validator_repo == snapshot_repo,
            f"validator={validator_repo or 'missing'} "
            f"snapshot={snapshot_repo or 'missing'}",
        )
    )
    checks.append(
        _check(
            "run_consistency",
            bool(validator_run) and validator_run == snapshot_run,
            f"validator={validator_run or 'missing'} "
            f"snapshot={snapshot_run or 'missing'}",
        )
    )
    checks.append(
        _check(
            "main_branch_scope",
            str(snapshot.get("branch") or "") == "main"
            and snapshot.get("current_pr") is None,
            f"branch={snapshot.get('branch') or 'missing'} "
            f"current_pr={snapshot.get('current_pr')!r}",
        )
    )

    validator_epoch = _epoch(validator.get("generated_at_epoch"))
    snapshot_epoch = _epoch(snapshot.get("generated_at_epoch"))
    timestamps_present = validator_epoch is not None and snapshot_epoch is not None
    within_future_bound = (
        timestamps_present
        and validator_epoch <= now + max_clock_skew_seconds
        and snapshot_epoch <= now + max_clock_skew_seconds
    )
    ordered = timestamps_present and snapshot_epoch >= validator_epoch
    checks.append(
        _check(
            "temporal_consistency",
            bool(timestamps_present and within_future_bound and ordered),
            f"validator={validator_epoch} snapshot={snapshot_epoch} "
            f"observed={now} skew={max_clock_skew_seconds}",
        )
    )

    validator_status = str(validator.get("status") or "").lower()
    snapshot_status = str(snapshot.get("status") or "").lower()
    if validator_status == "passed":
        propagated = (
            snapshot_status == "passed"
            and snapshot.get("critical_evidence") == "present"
            and snapshot.get("dominant_blocker") == "none"
        )
    else:
        propagated = (
            validator_status == "blocked"
            and snapshot_status == "blocked"
            and snapshot.get("critical_evidence") != "present"
        )
    checks.append(
        _check(
            "status_propagation",
            propagated,
            f"validator={validator_status or 'missing'} "
            f"snapshot={snapshot_status or 'missing'} "
            f"critical_evidence={snapshot.get('critical_evidence') or 'missing'}",
        )
    )

    failed = [item for item in checks if not item["ok"]]
    ready = not failed
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-single-state-consolidators-integrity",
        "generated_at_epoch": now,
        "status": "passed" if ready else "blocked",
        "ready": ready,
        "decision": (
            "single_state_consolidators_consistent"
            if ready
            else "single_state_consolidators_inconsistent"
        ),
        "repo": validator_repo or snapshot_repo,
        "sha": validator_sha or snapshot_sha,
        "github_run_id": validator_run or snapshot_run or None,
        "checks": checks,
        "blocking_issues": [item["id"] for item in failed],
        "automatic_state_promotion_allowed": False,
        "production_touched": False,
        "guardrails": [
            "fail_closed",
            "artifact_contract_validation",
            "sha_and_run_correlation",
            "temporal_consistency",
            "no_runtime_mutation",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Estado Único ReqSys — Integridade dos Consolidadores",
        "",
        f"- Status: `{report['status']}`",
        f"- Decision: `{report['decision']}`",
        f"- SHA: `{report['sha']}`",
        f"- Run ID: `{report['github_run_id']}`",
        f"- Production touched: `{str(report['production_touched']).lower()}`",
        "",
        "## Checks",
    ]
    for check in report["checks"]:
        lines.append(
            f"- `{check['status']}` {check['id']} — {check['detail']}"
        )
    if report["blocking_issues"]:
        lines.extend(["", "## Blocking issues"])
        lines.extend(f"- `{item}`" for item in report["blocking_issues"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate ReqSys single-state consolidator artifacts"
    )
    parser.add_argument("--validator", default=DEFAULT_VALIDATOR)
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--max-clock-skew-seconds", type=int, default=300)
    args = parser.parse_args()

    validator, validator_error = load_json_object(args.validator)
    snapshot, snapshot_error = load_json_object(args.snapshot)
    report = evaluate_consolidators(
        validator,
        snapshot,
        validator_error=validator_error,
        snapshot_error=snapshot_error,
        max_clock_skew_seconds=args.max_clock_skew_seconds,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output.parent / "summary.md").write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "decision": report["decision"],
                "blocking_issues": report["blocking_issues"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
