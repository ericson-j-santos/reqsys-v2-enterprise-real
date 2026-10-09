"""Admission control for duplicate physical Teams DEV E2E issue commands.

Pure decision logic keeps comment-id isolation in the gateway's concurrency
group. This guard only suppresses an *additional* identical authorized command
received within a short window; it never creates/cancels workflow runs.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

COMMAND = "/reqsys run pc24x7-teams-e2e-dev"
ISSUE_NUMBER = 1705
OWNER_LOGIN = "ericson-j-santos"
DUPLICATE_WINDOW_SECONDS = 120


class AdmissionError(ValueError):
    """Invalid or incomplete admission evidence; dispatch must fail closed."""


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise AdmissionError("comment_timestamp_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AdmissionError("comment_timestamp_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AdmissionError("comment_timestamp_without_timezone")
    return parsed.astimezone(timezone.utc)


def decide(
    event: dict[str, Any],
    comments: list[dict[str, Any]],
    *,
    expected_sha: str,
    window_seconds: int = DUPLICATE_WINDOW_SECONDS,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise AdmissionError("expected_main_sha_invalid")
    if not isinstance(window_seconds, int) or window_seconds <= 0:
        raise AdmissionError("duplicate_window_invalid")
    if event.get("action") != "created":
        raise AdmissionError("unexpected_issue_event_action")
    issue = event.get("issue")
    comment = event.get("comment")
    if not isinstance(issue, dict) or issue.get("number") != ISSUE_NUMBER:
        raise AdmissionError("issue_not_allowlisted")
    if not isinstance(comment, dict):
        raise AdmissionError("comment_missing")
    author = comment.get("user")
    if not isinstance(author, dict) or author.get("login") != OWNER_LOGIN:
        raise AdmissionError("comment_author_not_allowlisted")
    if comment.get("body") != COMMAND:
        raise AdmissionError("command_not_allowlisted")
    event_id = comment.get("id")
    if type(event_id) is not int or event_id <= 0:
        raise AdmissionError("comment_id_invalid")
    event_at = _timestamp(comment.get("created_at"))
    if not isinstance(comments, list):
        raise AdmissionError("comments_list_invalid")

    seen_current = 0
    older: list[int] = []
    for candidate in comments:
        if not isinstance(candidate, dict):
            raise AdmissionError("comment_record_invalid")
        candidate_id = candidate.get("id")
        if type(candidate_id) is not int or candidate_id <= 0:
            raise AdmissionError("comment_record_id_invalid")
        candidate_at = _timestamp(candidate.get("created_at"))
        if candidate_id == event_id:
            seen_current += 1
            if candidate_at != event_at:
                raise AdmissionError("event_comment_timestamp_mismatch")
            continue
        delta = event_at - candidate_at
        if candidate_id < event_id and timedelta(0) <= delta <= timedelta(seconds=window_seconds):
            older.append(candidate_id)

    if seen_current != 1:
        raise AdmissionError("current_comment_not_uniquely_read_back")

    canonical_id = min(older) if older else event_id
    return {
        "admitted": not older,
        "status": "duplicate_suppressed" if older else "admitted",
        "canonical_comment_id": canonical_id,
        "event_comment_id": event_id,
        "expected_sha": expected_sha,
        "window_seconds": window_seconds,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-file", required=True, type=Path)
    parser.add_argument("--comments-file", required=True, type=Path)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--github-output", required=True, type=Path)
    args = parser.parse_args()
    try:
        event = json.loads(args.event_file.read_text(encoding="utf-8"))
        comments = [
            json.loads(line) for line in args.comments_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        result = decide(event, comments, expected_sha=args.expected_sha)
    except (AdmissionError, OSError, TypeError, json.JSONDecodeError) as exc:
        # Never log raw comment bodies, request payloads, or provider values.
        reason = str(exc) if isinstance(exc, AdmissionError) else "admission_evidence_unavailable"
        parser.exit(2, "teams_e2e_admission_blocked:" + reason + "\n")

    with args.github_output.open("a", encoding="utf-8") as out:
        out.write("admitted=" + str(result["admitted"]).lower() + "\n")
        out.write("canonical_comment_id=" + str(result["canonical_comment_id"]) + "\n")
        out.write("window_seconds=" + str(result["window_seconds"]) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
