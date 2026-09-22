#!/usr/bin/env python3
"""Resolve códigos canônicos ReqSys a partir dos PRs associados a um SHA.

O workflow consulta a API GitHub `commits/{sha}/pulls` e entrega o JSON a este
script. Nenhum vínculo é inferido fora do padrão explícito REQ-#########.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REQUIREMENT_RE = re.compile(r"\bREQ-[0-9]{9}\b", re.IGNORECASE)


def resolve_requirement_codes(pulls: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    codes: set[str] = set()
    sources: list[dict[str, Any]] = []

    for pr in pulls:
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        fields = {
            "title": str(pr.get("title") or ""),
            "body": str(pr.get("body") or ""),
            "head_ref": str(head.get("ref") or ""),
        }
        found = sorted({match.group(0).upper() for value in fields.values() for match in REQUIREMENT_RE.finditer(value)})
        if not found:
            continue
        codes.update(found)
        sources.append(
            {
                "pr_number": pr.get("number"),
                "pr_url": pr.get("html_url"),
                "codes": found,
            }
        )

    return sorted(codes), sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve REQ-######### a partir de PRs associados ao SHA")
    parser.add_argument("--pulls-json", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    data = json.loads(Path(args.pulls_json).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("O JSON de PRs deve ser uma lista")

    codes, sources = resolve_requirement_codes(data)
    payload = {"requirement_codes": codes, "sources": sources, "count": len(codes)}
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for code in codes:
        print(code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
