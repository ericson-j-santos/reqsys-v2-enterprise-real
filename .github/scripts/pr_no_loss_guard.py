from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPLACEMENT_RE = re.compile(r"(?im)^\s*(?:substitu[ií]do\s+por|replacement\s+pr)\s*:\s*#(\d+)\s*$")
ABSORBED_COMMIT_RE = re.compile(r"(?im)^\s*(?:absorvido\s+por\s+commit|absorbed\s+by\s+commit)\s*:\s*([0-9a-f]{7,40})\s*$")
EXEMPT_LABEL = "closure-evidence:verified"
BLOCKED_LABEL = "closure-blocked:no-loss-evidence"


def parse_evidence(body: str | None) -> dict[str, str | int | None]:
    text = body or ""
    replacement = REPLACEMENT_RE.search(text)
    absorbed = ABSORBED_COMMIT_RE.search(text)
    return {
        "replacement_pr": int(replacement.group(1)) if replacement else None,
        "absorbed_commit": absorbed.group(1) if absorbed else None,
    }


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def _gh_json(endpoint: str) -> Any:
    result = _run("gh", "api", endpoint)
    return json.loads(result.stdout)


def _label_names(pr: dict[str, Any]) -> set[str]:
    return {str(item.get("name")) for item in pr.get("labels", []) if item.get("name")}


def replacement_is_valid(repo: str, current_number: int, replacement_number: int) -> tuple[bool, str]:
    if replacement_number == current_number:
        return False, "PR substituta não pode ser a própria PR."
    try:
        replacement = _gh_json(f"repos/{repo}/pulls/{replacement_number}")
    except subprocess.CalledProcessError:
        return False, f"PR substituta #{replacement_number} não foi encontrada."

    if replacement.get("merged_at"):
        return True, f"conteúdo rastreado por PR substituta #{replacement_number}, já integrada"
    if replacement.get("state") == "open":
        return True, f"conteúdo rastreado por PR substituta #{replacement_number}, ainda aberta"
    return False, f"PR substituta #{replacement_number} também está fechada sem integração."


def commit_is_in_main(commit: str) -> tuple[bool, str]:
    try:
        _run("git", "fetch", "origin", "main", "--quiet")
        _run("git", "fetch", "origin", commit, "--quiet")
        result = _run("git", "merge-base", "--is-ancestor", commit, "origin/main", check=False)
    except subprocess.CalledProcessError as exc:
        return False, f"não foi possível validar o commit informado: {exc}"
    if result.returncode == 0:
        return True, f"commit {commit[:12]} está contido em main"
    return False, f"commit {commit[:12]} não está contido em main"


def reopen_pr(repo: str, number: int, reason: str) -> None:
    _run("gh", "api", "-X", "PATCH", f"repos/{repo}/pulls/{number}", "-f", "state=open")
    _run(
        "gh",
        "api",
        "-X",
        "POST",
        f"repos/{repo}/issues/{number}/labels",
        "-f",
        f"labels[]={BLOCKED_LABEL}",
        check=False,
    )
    body = (
        "Fechamento revertido automaticamente para evitar perda de implementação.\n\n"
        f"Motivo: {reason}\n\n"
        "Para fechar sem merge, registre no corpo da PR uma evidência válida em uma destas formas:\n"
        "- `Substituído por: #1234` — a PR substituta precisa estar aberta ou integrada; ou\n"
        "- `Absorvido por commit: <sha>` — o commit precisa estar contido em `main`.\n\n"
        f"Alternativamente, use o rótulo `{EXEMPT_LABEL}` somente após validação humana documentada."
    )
    _run(
        "gh",
        "api",
        "-X",
        "POST",
        f"repos/{repo}/issues/{number}/comments",
        "-f",
        f"body={body}",
        check=False,
    )


def evaluate(event: dict[str, Any], repo: str) -> tuple[bool, str]:
    pr = event.get("pull_request") or {}
    number = int(pr.get("number") or event.get("number") or 0)
    if pr.get("merged") is True or pr.get("merged_at"):
        return True, "PR integrada; nenhuma proteção adicional necessária."
    if EXEMPT_LABEL in _label_names(pr):
        return True, f"fechamento explicitamente validado pelo rótulo {EXEMPT_LABEL}"

    evidence = parse_evidence(pr.get("body"))
    replacement = evidence["replacement_pr"]
    if isinstance(replacement, int):
        return replacement_is_valid(repo, number, replacement)

    commit = evidence["absorbed_commit"]
    if isinstance(commit, str):
        return commit_is_in_main(commit)

    return False, "não há prova de PR substituta nem commit absorvido pela main"


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not event_path or not repo:
        print("GITHUB_EVENT_PATH e GITHUB_REPOSITORY são obrigatórios.", file=sys.stderr)
        return 2

    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pr = event.get("pull_request") or {}
    number = int(pr.get("number") or event.get("number") or 0)
    if not number:
        print("Número da PR ausente.", file=sys.stderr)
        return 2

    allowed, reason = evaluate(event, repo)
    print(f"PR #{number}: {reason}")
    if allowed:
        return 0

    reopen_pr(repo, number, reason)
    print(f"PR #{number} reaberta para impedir perda de implementação.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
