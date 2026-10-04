#!/usr/bin/env python3
"""PR Auto Recovery replacement planning.

Consumes the read-only diagnostics report and produces a review-only planning
artifact for future draft replacement work. This script only writes local report
files inside the workflow workspace.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODE = "draft-replacement-plan-review-only"
MUTATING_ACTIONS_DISABLED = True


@dataclass(frozen=True)
class ReplacementCandidate:
    source_pr: int
    source_title: str
    source_url: str
    severity: str
    reasons: list[str]
    source_head_ref: str
    source_head_sha: str
    target_base_ref: str
    proposed_branch: str
    proposed_pr_title: str
    action: str
    requires_human_review: bool


def slugify(value: str, fallback: str) -> str:
    text = value.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:60] or fallback


def load_diagnostics(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Diagnostics file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("mutating_actions_disabled") is not True:
        raise ValueError("Diagnostics must be read-only")
    return payload


def should_plan(signal: dict[str, Any]) -> bool:
    if signal.get("severity") != "P0":
        return False
    reasons = [str(reason) for reason in signal.get("reasons") or []]
    return bool(reasons)


def build_candidate(signal: dict[str, Any]) -> ReplacementCandidate:
    number = int(signal["number"])
    title = str(signal.get("title") or f"PR {number}")
    proposed_branch = f"bot/recovery/pr-{number}-{slugify(title, f'pr-{number}')}"
    return ReplacementCandidate(
        source_pr=number,
        source_title=title,
        source_url=str(signal.get("url") or ""),
        severity=str(signal.get("severity") or "unknown"),
        reasons=[str(reason) for reason in signal.get("reasons") or []],
        source_head_ref=str(signal.get("head_ref") or ""),
        source_head_sha=str(signal.get("head_sha") or ""),
        target_base_ref=str(signal.get("base_ref") or "main"),
        proposed_branch=proposed_branch,
        proposed_pr_title=f"recovery: draft replacement for PR #{number}",
        action="PLAN_ONLY_REVIEW_REQUIRED",
        requires_human_review=True,
    )


def build_plan(diagnostics: dict[str, Any]) -> dict[str, Any]:
    candidates = [build_candidate(signal) for signal in diagnostics.get("signals", []) if should_plan(signal)]
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": MODE,
        "source_mode": diagnostics.get("mode"),
        "mutating_actions_disabled": MUTATING_ACTIONS_DISABLED,
        "candidate_count": len(candidates),
        "requires_human_review": True,
        "safety_profile": "review-only local artifacts",
        "candidates": [asdict(candidate) for candidate in candidates],
    }


def write_outputs(plan: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "replacement-plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# PR Auto Recovery Replacement Plan",
        "",
        f"Generated at: `{plan['generated_at']}`",
        f"Mode: `{plan['mode']}`",
        f"Mutating actions disabled: `{plan['mutating_actions_disabled']}`",
        f"Candidates: `{plan['candidate_count']}`",
        "",
        "| Source PR | Severity | Proposed branch | Action | Human review |",
        "|---:|---:|---|---|---:|",
    ]
    for candidate in plan["candidates"]:
        lines.append(
            f"| [#{candidate['source_pr']}]({candidate['source_url']}) | `{candidate['severity']}` | "
            f"`{candidate['proposed_branch']}` | `{candidate['action']}` | `{candidate['requires_human_review']}` |"
        )
    if not plan["candidates"]:
        lines.append("| n/a | n/a | n/a | `NO_REPLACEMENT_REQUIRED` | `True` |")
    (output_dir / "replacement-plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate PR replacement planning artifacts.")
    parser.add_argument("--diagnostics", default="artifacts/pr-auto-recovery/pr-auto-recovery.json")
    parser.add_argument("--output-dir", default="artifacts/pr-auto-recovery")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_plan(load_diagnostics(Path(args.diagnostics)))
    write_outputs(plan, Path(args.output_dir))
    print(json.dumps({"mode": plan["mode"], "candidate_count": plan["candidate_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
