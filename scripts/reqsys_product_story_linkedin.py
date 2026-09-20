#!/usr/bin/env python3
"""Approval Gate e adaptador oficial da LinkedIn Posts API para o Product Story Engine.

O modo padrão é dry-run. Publicação real exige:
- aprovação humana explícita;
- REQSYS_LINKEDIN_PUBLISH_ENABLED=true;
- LINKEDIN_ACCESS_TOKEN;
- ledger local sem publicação prévia para o mesmo content_hash.

O workflow governado deste incremento não habilita publicação real.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"
DEFAULT_LINKEDIN_VERSION = "202609"
RESTLI_PROTOCOL_VERSION = "2.0.0"


class ApprovalError(ValueError):
    pass


class LinkedInPublishError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


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
        "approved_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
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


def execute(
    *,
    report: dict[str, Any],
    content_hash: str,
    approved_by: str,
    correlation_id: str,
    confirmation: str,
    approval_kind: str,
    author_urn: str,
    mode: str,
    api_version: str,
    ledger_path: Path,
    opener=urlopen,
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

    base_result = {
        "schema_version": 1,
        "engine": "reqsys-product-story-linkedin-adapter",
        "mode": mode,
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
            "previous_publication": previous,
        },
    }

    if mode == "dry_run":
        return {
            **base_result,
            "status": "DRY_RUN_APPROVED",
            "published": False,
            "post_id": None,
        }

    if mode != "publish":
        raise ApprovalError("mode_invalid")
    if approval_kind != "human":
        raise ApprovalError("publish_requires_human_approval")
    if os.environ.get("REQSYS_LINKEDIN_PUBLISH_ENABLED", "").casefold() != "true":
        raise LinkedInPublishError("REQSYS_LINKEDIN_PUBLISH_ENABLED != true")
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    if previous:
        return {
            **base_result,
            "status": "ALREADY_PUBLISHED",
            "published": True,
            "post_id": _text(previous.get("post_id")),
        }

    post_id = publish_post(
        payload=payload,
        token=token,
        api_version=api_version,
        opener=opener,
    )
    publication = {
        "post_id": post_id,
        "published_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "approved_by": approval["approved_by"],
        "correlation_id": approval["correlation_id"],
        "api_version": api_version,
    }
    ledger.setdefault("publications", {})[approval["content_hash"]] = publication
    write_ledger(ledger_path, ledger)
    return {
        **base_result,
        "status": "PUBLISHED",
        "published": True,
        "post_id": post_id,
        "idempotency": {
            "key": approval["content_hash"],
            "previous_publication": None,
            "ledger_record": publication,
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
    )
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
        result = execute(
            report=report,
            content_hash=args.content_hash,
            approved_by=args.approved_by,
            correlation_id=args.correlation_id,
            confirmation=args.confirmation,
            approval_kind=args.approval_kind,
            author_urn=args.author_urn,
            mode=args.mode,
            api_version=args.api_version,
            ledger_path=args.ledger,
        )
    except (OSError, json.JSONDecodeError, ValueError, ApprovalError, LinkedInPublishError) as exc:
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
