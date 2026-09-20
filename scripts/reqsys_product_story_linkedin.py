#!/usr/bin/env python3
"""Approval Gate e adaptador governado da LinkedIn Posts API.

O workflow deste incremento executa somente dry-run. O caminho de publicação
real existe no adapter, mas falha fechado sem aprovação humana, feature flag,
token do LinkedIn e ledger persistente no GitHub Issue #1862.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"
DEFAULT_LINKEDIN_VERSION = "202609"
RESTLI_PROTOCOL_VERSION = "2.0.0"
GITHUB_API_URL = "https://api.github.com"
DEFAULT_LEDGER_ISSUE = 1862
LEDGER_MARKER_RE = re.compile(r"<!-- reqsys-product-story-ledger:(\{.*?\}) -->", re.DOTALL)


class ApprovalError(ValueError):
    pass


class LinkedInPublishError(RuntimeError):
    pass


class LedgerError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: objeto JSON esperado")
    return payload


def find_candidate(report: dict[str, Any], content_hash: str) -> dict[str, Any]:
    expected = _text(content_hash)
    if len(expected) != 64:
        raise ApprovalError("content_hash inválido")
    candidates = report.get("candidates")
    if not isinstance(candidates, list):
        raise ApprovalError("artifact sem candidates")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        linkedin = candidate.get("linkedin")
        if isinstance(linkedin, dict) and _text(linkedin.get("content_hash")) == expected:
            return candidate
    raise ApprovalError("candidate_not_found")


def build_approval(
    *,
    candidate: dict[str, Any],
    approved_by: str,
    correlation_id: str,
    confirmation: str,
    approval_kind: str,
) -> dict[str, Any]:
    approver = _text(approved_by)
    correlation = _text(correlation_id)
    kind = _text(approval_kind)
    if confirmation != "APPROVE":
        raise ApprovalError("confirmation_must_equal_APPROVE")
    if not approver:
        raise ApprovalError("approved_by_required")
    if not correlation:
        raise ApprovalError("correlation_id_required")
    if kind not in {"human", "test"}:
        raise ApprovalError("approval_kind_invalid")
    if candidate.get("status") != "READY_FOR_HUMAN_REVIEW":
        raise ApprovalError("candidate_not_ready_for_human_review")
    if candidate.get("selected_for_review") is not True:
        raise ApprovalError("candidate_not_selected_for_review")
    linkedin = candidate.get("linkedin")
    if not isinstance(linkedin, dict) or len(_text(linkedin.get("content_hash"))) != 64:
        raise ApprovalError("candidate_content_hash_invalid")
    return {
        "decision": "APPROVED",
        "approval_kind": kind,
        "approved_by": approver,
        "approved_at": _now(),
        "correlation_id": correlation,
        "content_hash": _text(linkedin.get("content_hash")),
        "pr_number": int(candidate.get("pr_number") or 0),
        "source_head_sha": _text((candidate.get("source") or {}).get("head_sha")),
    }


def validate_author_urn(author_urn: str) -> str:
    value = _text(author_urn)
    if value.startswith("urn:li:person:") and len(value) > len("urn:li:person:"):
        return value
    if value.startswith("urn:li:organization:") and len(value) > len("urn:li:organization:"):
        return value
    raise ApprovalError("author_urn deve ser urn:li:person:* ou urn:li:organization:*")


def build_linkedin_payload(candidate: dict[str, Any], author_urn: str) -> dict[str, Any]:
    linkedin = candidate.get("linkedin")
    if not isinstance(linkedin, dict):
        raise ApprovalError("candidate_linkedin_missing")
    commentary = _text(linkedin.get("post_text"))
    if not commentary:
        raise ApprovalError("post_text_required")
    return {
        "author": validate_author_urn(author_urn),
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


def build_linkedin_headers(*, token: str, api_version: str) -> dict[str, str]:
    bearer = _text(token)
    version = _text(api_version)
    if not bearer:
        raise LinkedInPublishError("LINKEDIN_ACCESS_TOKEN ausente")
    if len(version) != 6 or not version.isdigit():
        raise LinkedInPublishError("Linkedin-Version deve usar YYYYMM")
    return {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": RESTLI_PROTOCOL_VERSION,
        "Linkedin-Version": version,
    }


def publish_post(
    *,
    payload: dict[str, Any],
    token: str,
    api_version: str,
    opener=urlopen,
    timeout: int = 30,
) -> str:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        LINKEDIN_POSTS_URL,
        data=data,
        method="POST",
        headers=build_linkedin_headers(token=token, api_version=api_version),
    )
    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            post_id = _text(response.headers.get("x-restli-id"))
            if status != 201:
                raise LinkedInPublishError(f"LinkedIn Posts API status inesperado: {status}")
            if not post_id:
                raise LinkedInPublishError("LinkedIn Posts API sem x-restli-id")
            return post_id
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise LinkedInPublishError(f"LinkedIn Posts API HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise LinkedInPublishError(f"LinkedIn Posts API indisponível: {exc}") from exc


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "publications": {}}
    payload = load_json(path)
    publications = payload.get("publications")
    if not isinstance(publications, dict):
        raise LinkedInPublishError("ledger.publications inválido")
    return payload


def write_ledger(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def already_published(ledger: dict[str, Any], content_hash: str) -> dict[str, Any] | None:
    publications = ledger.get("publications") or {}
    item = publications.get(content_hash)
    return item if isinstance(item, dict) else None


def _github_headers(token: str) -> dict[str, str]:
    value = _text(token)
    if not value:
        raise LedgerError("GITHUB_TOKEN ausente para ledger persistente")
    return {
        "Authorization": f"Bearer {value}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "reqsys-product-story-ledger",
    }


def _github_json(
    *,
    url: str,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    opener=urlopen,
    timeout: int = 30,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, method=method, headers=_github_headers(token))
    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            raw = response.read().decode("utf-8") if hasattr(response, "read") else ""
            parsed = json.loads(raw) if raw else None
            return status, parsed
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise LedgerError(f"GitHub ledger HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LedgerError(f"GitHub ledger indisponível/inválido: {exc}") from exc


def ledger_marker(entry: dict[str, Any]) -> str:
    compact = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"<!-- reqsys-product-story-ledger:{compact} -->"


def ledger_comment(entry: dict[str, Any]) -> str:
    return (
        f"{ledger_marker(entry)}\n"
        f"Product Story publication ledger — **{entry['state']}**\n\n"
        f"- content_hash: `{entry['content_hash']}`\n"
        f"- correlation_id: `{entry['correlation_id']}`\n"
        f"- approved_by: `{entry['approved_by']}`\n"
        f"- post_id: `{entry.get('post_id') or 'n/a'}`\n"
        f"- updated_at: `{entry['updated_at']}`"
    )


def parse_ledger_entry(body: str) -> dict[str, Any] | None:
    match = LEDGER_MARKER_RE.search(_text(body))
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def list_github_ledger_entries(
    *,
    repository: str,
    issue_number: int,
    token: str,
    opener=urlopen,
) -> list[dict[str, Any]]:
    if "/" not in repository:
        raise LedgerError("ledger repository inválido")
    entries: list[dict[str, Any]] = []
    for page in range(1, 11):
        url = (
            f"{GITHUB_API_URL}/repos/{repository}/issues/{issue_number}/comments"
            f"?per_page=100&page={page}"
        )
        status, payload = _github_json(url=url, token=token, opener=opener)
        if status != 200 or not isinstance(payload, list):
            raise LedgerError(f"resposta inválida ao ler ledger: status={status}")
        for comment in payload:
            if not isinstance(comment, dict):
                continue
            entry = parse_ledger_entry(_text(comment.get("body")))
            if entry:
                entry["_comment_id"] = int(comment.get("id") or 0)
                entries.append(entry)
        if len(payload) < 100:
            break
    return entries


def find_persistent_entry(entries: list[dict[str, Any]], content_hash: str) -> dict[str, Any] | None:
    matches = [e for e in entries if _text(e.get("content_hash")) == content_hash]
    if not matches:
        return None
    return matches[-1]


def reserve_github_ledger(
    *,
    repository: str,
    issue_number: int,
    token: str,
    approval: dict[str, Any],
    opener=urlopen,
) -> dict[str, Any]:
    entries = list_github_ledger_entries(
        repository=repository,
        issue_number=issue_number,
        token=token,
        opener=opener,
    )
    existing = find_persistent_entry(entries, approval["content_hash"])
    if existing:
        state = _text(existing.get("state"))
        if state == "PUBLISHED":
            return {"already_published": True, "entry": existing}
        if state in {"PREPARED", "RECONCILE_REQUIRED"}:
            raise LedgerError(f"ledger bloqueia retry automático: state={state}")

    entry = {
        "schema_version": 1,
        "state": "PREPARED",
        "content_hash": approval["content_hash"],
        "correlation_id": approval["correlation_id"],
        "approved_by": approval["approved_by"],
        "pr_number": approval["pr_number"],
        "source_head_sha": approval["source_head_sha"],
        "post_id": None,
        "updated_at": _now(),
    }
    url = f"{GITHUB_API_URL}/repos/{repository}/issues/{issue_number}/comments"
    status, payload = _github_json(
        url=url,
        token=token,
        method="POST",
        payload={"body": ledger_comment(entry)},
        opener=opener,
    )
    if status != 201 or not isinstance(payload, dict) or not int(payload.get("id") or 0):
        raise LedgerError(f"falha ao reservar ledger persistente: status={status}")
    entry["_comment_id"] = int(payload["id"])
    return {"already_published": False, "entry": entry}


def update_github_ledger_entry(
    *,
    repository: str,
    comment_id: int,
    token: str,
    entry: dict[str, Any],
    opener=urlopen,
) -> dict[str, Any]:
    url = f"{GITHUB_API_URL}/repos/{repository}/issues/comments/{comment_id}"
    status, payload = _github_json(
        url=url,
        token=token,
        method="PATCH",
        payload={"body": ledger_comment(entry)},
        opener=opener,
    )
    if status != 200 or not isinstance(payload, dict):
        raise LedgerError(f"falha ao atualizar ledger persistente: status={status}")
    result = dict(entry)
    result["_comment_id"] = comment_id
    return result


def execute_dry_run(
    *,
    report: dict[str, Any],
    content_hash: str,
    approved_by: str,
    correlation_id: str,
    confirmation: str,
    approval_kind: str,
    author_urn: str,
    api_version: str,
    ledger_path: Path,
) -> dict[str, Any]:
    candidate = find_candidate(report, content_hash)
    approval = build_approval(
        candidate=candidate,
        approved_by=approved_by,
        correlation_id=correlation_id,
        confirmation=confirmation,
        approval_kind=approval_kind,
    )
    payload = build_linkedin_payload(candidate, author_urn)
    ledger = load_ledger(ledger_path)
    previous = already_published(ledger, approval["content_hash"])
    return {
        "schema_version": 2,
        "engine": "reqsys-product-story-linkedin-adapter",
        "mode": "dry_run",
        "status": "DRY_RUN_APPROVED",
        "published": False,
        "post_id": None,
        "correlation_id": approval["correlation_id"],
        "content_hash": approval["content_hash"],
        "approval": approval,
        "linkedin": {
            "endpoint": LINKEDIN_POSTS_URL,
            "api_version": api_version,
            "restli_protocol_version": RESTLI_PROTOCOL_VERSION,
            "author_urn": payload["author"],
            "payload": payload,
        },
        "idempotency": {
            "key": approval["content_hash"],
            "backend": "local_dry_run",
            "previous_publication": previous,
        },
    }


def execute_publish(
    *,
    report: dict[str, Any],
    content_hash: str,
    approved_by: str,
    correlation_id: str,
    confirmation: str,
    approval_kind: str,
    author_urn: str,
    api_version: str,
    ledger_repository: str,
    ledger_issue: int,
    github_token: str,
    linkedin_token: str,
    linkedin_opener=urlopen,
    github_opener=urlopen,
) -> dict[str, Any]:
    candidate = find_candidate(report, content_hash)
    approval = build_approval(
        candidate=candidate,
        approved_by=approved_by,
        correlation_id=correlation_id,
        confirmation=confirmation,
        approval_kind=approval_kind,
    )
    if approval_kind != "human":
        raise ApprovalError("publish_requires_human_approval")
    if os.environ.get("REQSYS_LINKEDIN_PUBLISH_ENABLED", "").casefold() != "true":
        raise LinkedInPublishError("REQSYS_LINKEDIN_PUBLISH_ENABLED != true")
    payload = build_linkedin_payload(candidate, author_urn)

    reservation = reserve_github_ledger(
        repository=ledger_repository,
        issue_number=ledger_issue,
        token=github_token,
        approval=approval,
        opener=github_opener,
    )
    if reservation["already_published"]:
        previous = reservation["entry"]
        return {
            "schema_version": 2,
            "engine": "reqsys-product-story-linkedin-adapter",
            "mode": "publish",
            "status": "ALREADY_PUBLISHED",
            "published": True,
            "post_id": _text(previous.get("post_id")),
            "correlation_id": approval["correlation_id"],
            "content_hash": approval["content_hash"],
            "approval": approval,
            "idempotency": {
                "key": approval["content_hash"],
                "backend": "github_issue",
                "ledger_repository": ledger_repository,
                "ledger_issue": ledger_issue,
                "ledger_entry": previous,
            },
        }

    prepared = reservation["entry"]
    comment_id = int(prepared["_comment_id"])
    post_id = publish_post(
        payload=payload,
        token=linkedin_token,
        api_version=api_version,
        opener=linkedin_opener,
    )
    published_entry = {
        **{k: v for k, v in prepared.items() if not k.startswith("_")},
        "state": "PUBLISHED",
        "post_id": post_id,
        "updated_at": _now(),
    }
    try:
        final_entry = update_github_ledger_entry(
            repository=ledger_repository,
            comment_id=comment_id,
            token=github_token,
            entry=published_entry,
            opener=github_opener,
        )
    except LedgerError as exc:
        reconcile = {
            **published_entry,
            "state": "RECONCILE_REQUIRED",
            "updated_at": _now(),
        }
        try:
            update_github_ledger_entry(
                repository=ledger_repository,
                comment_id=comment_id,
                token=github_token,
                entry=reconcile,
                opener=github_opener,
            )
        except LedgerError:
            pass
        raise LedgerError(
            f"LinkedIn publicou post_id={post_id}, mas ledger requer reconciliação; "
            f"comment_id={comment_id}: {exc}"
        ) from exc

    return {
        "schema_version": 2,
        "engine": "reqsys-product-story-linkedin-adapter",
        "mode": "publish",
        "status": "PUBLISHED",
        "published": True,
        "post_id": post_id,
        "correlation_id": approval["correlation_id"],
        "content_hash": approval["content_hash"],
        "approval": approval,
        "linkedin": {
            "endpoint": LINKEDIN_POSTS_URL,
            "api_version": api_version,
            "restli_protocol_version": RESTLI_PROTOCOL_VERSION,
            "author_urn": payload["author"],
        },
        "idempotency": {
            "key": approval["content_hash"],
            "backend": "github_issue",
            "ledger_repository": ledger_repository,
            "ledger_issue": ledger_issue,
            "ledger_entry": final_entry,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--content-hash", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--confirmation", required=True)
    parser.add_argument("--approval-kind", choices=("human", "test"), required=True)
    parser.add_argument("--author-urn", required=True)
    parser.add_argument("--mode", choices=("dry_run", "publish"), default="dry_run")
    parser.add_argument("--api-version", default=DEFAULT_LINKEDIN_VERSION)
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("artifacts/reqsys-product-story-approval/publication-ledger.json"),
        help="Ledger local usado somente em dry-run/testes.",
    )
    parser.add_argument("--ledger-repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--ledger-issue", type=int, default=DEFAULT_LEDGER_ISSUE)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reqsys-product-story-approval/approval-result.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = load_json(args.input)
        if args.mode == "dry_run":
            result = execute_dry_run(
                report=report,
                content_hash=args.content_hash,
                approved_by=args.approved_by,
                correlation_id=args.correlation_id,
                confirmation=args.confirmation,
                approval_kind=args.approval_kind,
                author_urn=args.author_urn,
                api_version=args.api_version,
                ledger_path=args.ledger,
            )
        else:
            result = execute_publish(
                report=report,
                content_hash=args.content_hash,
                approved_by=args.approved_by,
                correlation_id=args.correlation_id,
                confirmation=args.confirmation,
                approval_kind=args.approval_kind,
                author_urn=args.author_urn,
                api_version=args.api_version,
                ledger_repository=args.ledger_repository,
                ledger_issue=args.ledger_issue,
                github_token=os.environ.get("GITHUB_TOKEN", ""),
                linkedin_token=os.environ.get("LINKEDIN_ACCESS_TOKEN", ""),
            )
    except (OSError, json.JSONDecodeError, ValueError, ApprovalError, LinkedInPublishError, LedgerError) as exc:
        print(f"PRODUCT_STORY_APPROVAL_FAILED: {exc}", file=sys.stderr)
        return 3

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "result": "OK",
                "status": result["status"],
                "content_hash": result["content_hash"],
                "published": result["published"],
                "post_id": result["post_id"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
