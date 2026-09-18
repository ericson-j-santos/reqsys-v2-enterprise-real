#!/usr/bin/env python3
"""Deterministic ReqSys GitLab task classifier.

This script is intentionally dependency-free so it can run in GitLab CI
without network access. It classifies a task into a suggested AI domain,
priority and branch prefix using keyword rules.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

DOMAIN_RULES = {
    "ia:runtime": ["deploy", "runtime", "health", "ambiente", "url", "container", "rollback"],
    "ia:observability": ["log", "trace", "metric", "observ", "dashboard", "artifact", "evidence"],
    "ia:ux": ["ui", "ux", "tela", "layout", "card", "responsiv", "drill"],
    "ia:governance-ci": ["ci", "pipeline", "workflow", "gate", "merge", "branch", "security"],
    "ia:autonomous": ["agent", "automacao", "remedi", "orquestr", "autonom"],
    "ia:docs": ["doc", "adr", "diagrama", "changelog", "arquitetura viva"],
}

PRIORITY_RULES = {
    "priority:P0": ["p0", "critico", "crítico", "producao", "produção", "deploy quebrado", "ci vermelho"],
    "priority:P1": ["p1", "importante", "governanca", "governança", "observabilidade", "runtime"],
    "priority:P2": ["p2", "melhoria", "documentacao", "documentação", "refino"],
}

BRANCH_PREFIX = {
    "ia:runtime": "runtime",
    "ia:observability": "observability",
    "ia:ux": "ux",
    "ia:governance-ci": "governance",
    "ia:autonomous": "agents",
    "ia:docs": "docs",
    "ia:coordinator": "coord",
}


def normalize(value: str) -> str:
    return value.lower().strip()


def score_rules(text: str, rules: dict[str, list[str]], fallback: str) -> str:
    normalized = normalize(text)
    scores = {label: 0 for label in rules}
    for label, keywords in rules.items():
        for keyword in keywords:
            if keyword in normalized:
                scores[label] += 1
    label, score = max(scores.items(), key=lambda item: item[1])
    return label if score > 0 else fallback


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "task"


def classify(task: str) -> dict[str, object]:
    domain = score_rules(task, DOMAIN_RULES, "ia:coordinator")
    priority = score_rules(task, PRIORITY_RULES, "priority:P1")
    branch = f"{BRANCH_PREFIX[domain]}/{slugify(task)}"
    return {
        "task": task,
        "ia_destino": domain,
        "prioridade": priority,
        "branch_recomendada": branch,
        "escopo_permitido": ["arquivos do dominio associado", "documentacao e testes relacionados"],
        "escopo_proibido": ["auth", "secrets", "producao", "workflows globais sem aprovacao"],
        "definition_of_done": [
            "pipeline verde",
            "sem conflito",
            "artifact publicado quando aplicavel",
            "documentacao atualizada",
            "revisao coordenadora",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default=os.getenv("REQSYS_TASK", "GitLab pipeline execution"))
    parser.add_argument("--mode", default="manual", choices=["manual", "pipeline"])
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    result = classify(args.task)
    result["mode"] = args.mode
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"

    if args.output == "-":
        print(content, end="")
    else:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
