#!/usr/bin/env python3
"""Gera drafts governados de apresentação do ReqSys a partir do log semanal evidenciado."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REQUIRED_DIMENSIONS = ("implemented", "validated", "evidenced", "consolidated")
SENSITIVE_TERMS = (
    "password",
    "senha",
    "secret",
    "segredo",
    "token",
    "credential",
    "credencial",
    "vault",
    "cofre",
    ".env",
    "desktop-pdqk954",
    "noteri",
)
HASHTAGS = "#ReqSys #EngenhariaDeSoftware #DevOps #Governanca #Automacao"


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _contains_sensitive_signal(item: dict[str, Any]) -> tuple[bool, list[str]]:
    haystacks = [_normalized_text(item.get("title")).casefold()]
    haystacks.extend(_normalized_text(path).casefold() for path in item.get("files", []))
    matches = sorted({term for term in SENSITIVE_TERMS if any(term in text for text in haystacks)})
    return bool(matches), matches


def _eligibility_blockers(item: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for dimension in REQUIRED_DIMENSIONS:
        if not bool(item.get(dimension)):
            blockers.append(f"{dimension}_required")
    if not _normalized_text(item.get("url")):
        blockers.append("pr_url_required")
    head_sha = _normalized_text(item.get("head_sha"))
    if len(head_sha) < 12:
        blockers.append("head_sha_required")
    gaps = [str(gap) for gap in item.get("evidence_gaps", []) if str(gap).strip()]
    if gaps:
        blockers.append("evidence_gaps_present")
    sensitive, matches = _contains_sensitive_signal(item)
    if sensitive:
        blockers.append("sensitive_signal:" + ",".join(matches))
    return blockers


def publicability_score(item: dict[str, Any]) -> int:
    """Score operacional para ordenar drafts; não representa qualidade do produto."""
    score = 0
    score += 5 if item.get("validated") else 0
    score += 5 if item.get("evidenced") else 0
    score += 5 if item.get("consolidated") else 0
    score += 3 if item.get("governed") else 0
    files = [_normalized_text(path) for path in item.get("files", [])]
    score += 2 if any(path.startswith(("docs/", "evidence/", "audit/", "reports/")) for path in files) else 0
    return score


def title_for_visual(item: dict[str, Any]) -> str:
    title = _normalized_text(item.get("title")) or "Entrega ReqSys"
    return title if len(title) <= 72 else title[:69].rstrip() + "..."


def render_post(item: dict[str, Any]) -> str:
    title = _normalized_text(item.get("title")) or "Entrega consolidada do ReqSys"
    number = int(item.get("number") or 0)
    head_sha = _normalized_text(item.get("head_sha"))
    short_sha = head_sha[:12] if head_sha else "ausente"
    governed_line = (
        "\n• controles de governança fazem parte da entrega"
        if item.get("governed")
        else ""
    )
    return (
        f"ReqSys: {title}\n\n"
        f"Uma nova entrega do ReqSys foi consolidada a partir da PR #{number}.\n\n"
        "O que está comprovado:\n"
        "• implementação integrada por Pull Request\n"
        "• validação automatizada concluída\n"
        f"• evidência vinculada ao SHA {short_sha}\n"
        "• documentação ou evidência versionada no repositório"
        f"{governed_line}\n\n"
        "A proposta do ReqSys é tornar a evolução do produto rastreável: "
        "não basta mudar código; a entrega precisa deixar evidência verificável.\n\n"
        f"{HASHTAGS}"
    )


def _content_hash(item: dict[str, Any], post: str) -> str:
    material = {
        "pr": int(item.get("number") or 0),
        "head_sha": _normalized_text(item.get("head_sha")),
        "post": post,
    }
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_candidate(item: dict[str, Any]) -> dict[str, Any]:
    blockers = _eligibility_blockers(item)
    post = render_post(item)
    status = "BLOCKED" if blockers else "READY_FOR_HUMAN_REVIEW"
    files = [_normalized_text(path) for path in item.get("files", []) if _normalized_text(path)]
    return {
        "pr_number": int(item.get("number") or 0),
        "title": _normalized_text(item.get("title")),
        "source": {
            "pr_url": _normalized_text(item.get("url")),
            "head_sha": _normalized_text(item.get("head_sha")),
            "merged_at": _normalized_text(item.get("merged_at")),
            "checks": item.get("checks", []),
            "files": files,
        },
        "evidence_state": {
            dimension: bool(item.get(dimension))
            for dimension in ("implemented", "validated", "evidenced", "consolidated", "governed")
        },
        "publicability_score": publicability_score(item),
        "status": status,
        "blockers": blockers,
        "selected_for_review": False,
        "approval": {
            "required": True,
            "approved": False,
            "published": False,
        },
        "linkedin": {
            "post_text": post,
            "content_hash": _content_hash(item, post),
        },
        "visual_brief": {
            "headline": title_for_visual(item),
            "subheadline": "Entrega consolidada com evidência verificável",
            "facts": [
                f"PR #{int(item.get('number') or 0)}",
                f"SHA {_normalized_text(item.get('head_sha'))[:12] or 'ausente'}",
                "Validação automatizada: sim" if item.get("validated") else "Validação automatizada: não",
                "Governança: sim" if item.get("governed") else "Governança: não",
            ],
        },
    }


def build_report(source_report: dict[str, Any], *, limit: int = 3) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("limit deve ser >= 1")
    raw_items = source_report.get("items", [])
    if not isinstance(raw_items, list):
        raise ValueError("items deve ser uma lista")

    candidates = [build_candidate(item) for item in raw_items if isinstance(item, dict)]
    ready = [c for c in candidates if c["status"] == "READY_FOR_HUMAN_REVIEW"]
    ready.sort(
        key=lambda c: (
            int(c["publicability_score"]),
            _normalized_text(c["source"].get("merged_at")),
            int(c["pr_number"]),
        ),
        reverse=True,
    )
    selected_keys = {(c["pr_number"], c["linkedin"]["content_hash"]) for c in ready[:limit]}
    for candidate in candidates:
        candidate["selected_for_review"] = (
            candidate["pr_number"],
            candidate["linkedin"]["content_hash"],
        ) in selected_keys

    return {
        "schema_version": "1.0.0",
        "engine": "reqsys-product-story-engine",
        "mode": "review_only",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": {
            "repository": _normalized_text(source_report.get("repository")),
            "window": source_report.get("window", {}),
            "generated_at": _normalized_text(source_report.get("generated_at")),
        },
        "policy": {
            "required_dimensions": list(REQUIRED_DIMENSIONS),
            "human_review_required": True,
            "automatic_publish": False,
            "selection_limit": limit,
            "score_meaning": "ordenação operacional; não representa qualidade do produto",
        },
        "summary": {
            "total_source_items": len(raw_items),
            "ready_for_human_review": len(ready),
            "blocked": sum(c["status"] == "BLOCKED" for c in candidates),
            "selected_for_review": sum(bool(c["selected_for_review"]) for c in candidates),
        },
        "candidates": candidates,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# ReqSys — Product Story Engine",
        "",
        f"- Modo: `{report['mode']}`",
        f"- Gerado em: `{report['generated_at']}`",
        f"- Itens de origem: `{summary['total_source_items']}`",
        f"- Prontos para revisão humana: `{summary['ready_for_human_review']}`",
        f"- Selecionados: `{summary['selected_for_review']}`",
        f"- Bloqueados: `{summary['blocked']}`",
        "",
        "> Nenhum conteúdo é publicado automaticamente. Todo draft exige revisão e aprovação humana.",
        "",
    ]
    selected = [c for c in report["candidates"] if c["selected_for_review"]]
    if not selected:
        lines += ["## Seleção", "", "Nenhuma entrega atende aos critérios de publicação nesta execução.", ""]
        return "\n".join(lines)

    lines += ["## Seleção", ""]
    for candidate in selected:
        lines += [
            f"### PR #{candidate['pr_number']} — {candidate['title']}",
            "",
            f"- Score operacional: `{candidate['publicability_score']}`",
            f"- SHA: `{candidate['source']['head_sha']}`",
            f"- Hash idempotente: `{candidate['linkedin']['content_hash']}`",
            "",
            "```text",
            candidate["linkedin"]["post_text"],
            "```",
            "",
        ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/reqsys-product-story-engine"))
    parser.add_argument("--limit", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        source_report = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(source_report, dict):
            raise ValueError("relatório de origem deve ser objeto JSON")
        report = build_report(source_report, limit=args.limit)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"PRODUCT_STORY_FAILED: {exc}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "product-story-candidates.json"
    md_path = args.output_dir / "product-story-candidates.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "result": "OK",
                "ready_for_human_review": report["summary"]["ready_for_human_review"],
                "selected_for_review": report["summary"]["selected_for_review"],
                "json": str(json_path),
                "markdown": str(md_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
