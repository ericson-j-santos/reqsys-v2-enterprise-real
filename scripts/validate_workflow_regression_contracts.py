#!/usr/bin/env python3
"""Valida contratos mínimos contra regressões em workflows críticos do ReqSys."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAMS_PAGINATED_WORKFLOWS = (
    ".github/workflows/teams-notification-slo.yml",
    ".github/workflows/teams-gold-certification.yml",
    ".github/workflows/teams-provisional-gold-certification.yml",
    ".github/workflows/teams-certification-progress-status.yml",
)


def fail(message: str) -> None:
    raise AssertionError(message)


def validate_cofre_runtime_gate() -> None:
    path = ROOT / ".github/workflows/cofre-runtime-evidence-gate.yml"
    text = path.read_text(encoding="utf-8")

    top_level_env = re.search(r"(?m)^env:\n(?P<body>(?:^[ \t]+.*\n?)*)", text)
    if top_level_env and "runner.temp" in top_level_env.group("body"):
        fail("Cofre Runtime Evidence Gate não pode usar runner.temp no env global")

    runtime_job = re.search(
        r"(?ms)^  runtime-evidence:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        text,
    )
    if not runtime_job:
        fail("Job runtime-evidence não encontrado")
    if "STATE_FILE:" not in runtime_job.group("body"):
        fail("STATE_FILE deve permanecer no escopo do job runtime-evidence")
    if "runner." in runtime_job.group("body"):
        fail(
            "Cofre Runtime Evidence Gate não pode usar contexto runner no env "
            "do job (não suportado pelo GitHub Actions em jobs.<id>.env)"
        )


def has_completed_workflow_run_trigger(text: str) -> bool:
    workflow_run = re.search(
        r"(?ms)^  workflow_run:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|^concurrency:|\Z)",
        text,
    )
    if not workflow_run:
        return False

    body = workflow_run.group("body")
    return bool(
        re.search(r"(?m)^    types:\s*\[\s*completed\s*\]\s*$", body)
        or re.search(r"(?m)^    types:\s*\n(?:^      - .*\n)*^      - completed\s*$", body)
    )


def validate_pr_evidence_gate() -> None:
    path = ROOT / ".github/workflows/pr-evidence-gate.yml"
    text = path.read_text(encoding="utf-8")

    if not has_completed_workflow_run_trigger(text):
        fail("PR Evidence Gate deve revalidar após workflow_run completed")
    if "deferred" not in text:
        fail("PR Evidence Gate deve representar timeout transitório como deferred")
    if re.search(r"gate\.failures\.push\(\.\.\.gate\.pending\).*gate\.status\s*=\s*['\"]failed['\"]", text, re.S):
        fail("PR Evidence Gate não pode converter pending em failure por timeout")

    strict_failure_is_blocking = (
        "strict_ci_failed" in text
        or "Strict workflow failed on current head SHA:" in text
    )
    if not strict_failure_is_blocking:
        fail("Falha real do CI estrito deve continuar bloqueante")


def validate_teams_paginated_workflow_queries() -> None:
    for relative_path in TEAMS_PAGINATED_WORKFLOWS:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        paginate_count = text.count('"--paginate"') + text.count("'--paginate'")
        slurp_count = text.count('"--slurp"') + text.count("'--slurp'")

        if paginate_count == 0:
            fail(f"Consulta paginada ausente em {relative_path}")
        if slurp_count < paginate_count:
            fail(f"Toda consulta --paginate deve usar --slurp em {relative_path}")
        if ".stdout.splitlines()" in text:
            fail(f"Saída JSON paginada não pode ser separada por linhas em {relative_path}")
        if not re.search(r"json\.loads\((?:completed|result)\.stdout\)", text):
            fail(f"Lista de páginas JSON deve ser decodificada integralmente em {relative_path}")


def validate_flow_completion_previous_state_isolation() -> None:
    relative_path = ".github/workflows/flow-completion-alert-lifecycle.yml"
    text = (ROOT / relative_path).read_text(encoding="utf-8")

    if "unzip -oq .tmp/previous.zip -d .tmp/previous/artifact" not in text:
        fail("Artifact anterior deve ser extraído fora do state.json de fallback")
    if "find .tmp/previous/artifact" not in text:
        fail("Busca do estado anterior deve permanecer isolada no diretório do artifact")
    if 'echo \'{}\' > .tmp/previous/state.json' not in text:
        fail("Estado anterior deve preservar fallback JSON vazio")


def main() -> int:
    checks = [
        validate_cofre_runtime_gate,
        validate_pr_evidence_gate,
        validate_teams_paginated_workflow_queries,
        validate_flow_completion_previous_state_isolation,
    ]
    failures: list[str] = []
    for check in checks:
        try:
            check()
            print(f"PASS {check.__name__}")
        except (AssertionError, OSError) as exc:
            failures.append(f"{check.__name__}: {exc}")
            print(f"FAIL {check.__name__}: {exc}", file=sys.stderr)

    if failures:
        print("\nWorkflow regression contract validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("All workflow regression contracts passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
