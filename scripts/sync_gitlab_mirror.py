#!/usr/bin/env python3
"""Sincroniza GitHub main -> GitLab main com política fail-closed.

Princípios:
- GitHub é a fonte canônica.
- Nunca executa force-push.
- Só avança GitLab se o HEAD remoto atual for ancestral do HEAD GitHub.
- Se GitLab possuir commit exclusivo/divergência, bloqueia sem alterar o remoto.
- Token é lido somente de variável de ambiente e nunca é persistido/logado.
- Gera evidência JSON para auditoria.

Uso:
    GITLAB_MIRROR_TOKEN=... python scripts/sync_gitlab_mirror.py
    python scripts/sync_gitlab_mirror.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_GITLAB_REPOSITORY = "https://gitlab.com/ericson-j-santos/reqsys-v2-enterprise-real.git"
DEFAULT_SOURCE_REF = "HEAD"
DEFAULT_TARGET_BRANCH = "main"
DEFAULT_EVIDENCE = "audit/gitlab-mirror-sync.json"


class SyncError(RuntimeError):
    pass


@dataclass
class Evidence:
    schema_version: str
    timestamp_utc: str
    correlation_id: str
    status: str
    action: str
    source_repository: str
    target_repository: str
    source_ref: str
    target_branch: str
    source_sha: str | None = None
    target_sha_before: str | None = None
    target_sha_after: str | None = None
    detail: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def correlation_id() -> str:
    explicit = os.getenv("CORRELATION_ID", "").strip()
    if explicit:
        return explicit
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    attempt = os.getenv("GITHUB_RUN_ATTEMPT", "1")
    return f"gitlab-mirror-{run_id}-{attempt}"


def run_git(args: Sequence[str], *, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if check and completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise SyncError(message)
    return completed


def resolve_sha(ref: str) -> str:
    return run_git(["rev-parse", ref]).stdout.strip()


def is_ancestor(ancestor: str, descendant: str) -> bool:
    completed = run_git(["merge-base", "--is-ancestor", ancestor, descendant], check=False)
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise SyncError(completed.stderr.strip() or "falha ao validar ancestralidade")


def classify_state(*, source_sha: str, target_sha: str, target_is_ancestor: bool) -> str:
    if source_sha == target_sha:
        return "in_sync"
    if target_is_ancestor:
        return "fast_forward"
    return "diverged"


def write_evidence(path: Path, evidence: Evidence) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(evidence), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_auth_env(token: str, askpass_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": str(askpass_path),
            "GITLAB_MIRROR_TOKEN": token,
        }
    )
    return env


def create_askpass(directory: Path) -> Path:
    path = directory / "git-askpass.sh"
    path.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  *Username*) printf '%s\\n' 'oauth2' ;;\n"
        "  *) printf '%s\\n' \"$GITLAB_MIRROR_TOKEN\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gitlab-repository", default=os.getenv("GITLAB_MIRROR_REPOSITORY", DEFAULT_GITLAB_REPOSITORY))
    parser.add_argument("--source-ref", default=DEFAULT_SOURCE_REF)
    parser.add_argument("--target-branch", default=DEFAULT_TARGET_BRANCH)
    parser.add_argument("--token-env", default="GITLAB_MIRROR_TOKEN")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence_path = Path(args.evidence)
    source_repo = os.getenv("GITHUB_REPOSITORY", "local")
    evidence = Evidence(
        schema_version="1.0.0",
        timestamp_utc=utc_now(),
        correlation_id=correlation_id(),
        status="running",
        action="none",
        source_repository=source_repo,
        target_repository=args.gitlab_repository,
        source_ref=args.source_ref,
        target_branch=args.target_branch,
    )

    try:
        source_sha = resolve_sha(args.source_ref)
        evidence.source_sha = source_sha

        token = os.getenv(args.token_env, "").strip()
        if not token:
            raise SyncError(f"variável protegida {args.token_env} não configurada")

        with tempfile.TemporaryDirectory(prefix="reqsys-gitlab-mirror-") as tmp:
            askpass = create_askpass(Path(tmp))
            auth_env = build_auth_env(token, askpass)
            remote_ref = "refs/remotes/gitlab-mirror/main"

            run_git(
                ["fetch", "--no-tags", "--prune", args.gitlab_repository, f"refs/heads/{args.target_branch}:{remote_ref}"],
                env=auth_env,
            )
            target_sha = resolve_sha(remote_ref)
            evidence.target_sha_before = target_sha

            state = classify_state(
                source_sha=source_sha,
                target_sha=target_sha,
                target_is_ancestor=is_ancestor(target_sha, source_sha),
            )

            if state == "in_sync":
                evidence.status = "passed"
                evidence.action = "noop"
                evidence.target_sha_after = target_sha
                evidence.detail = "GitLab já está sincronizado com o GitHub."
                write_evidence(evidence_path, evidence)
                print(json.dumps(asdict(evidence), ensure_ascii=False))
                return 0

            if state == "diverged":
                evidence.status = "blocked"
                evidence.action = "none"
                evidence.target_sha_after = target_sha
                evidence.detail = "GitLab contém commit exclusivo ou histórico divergente; force-push é proibido."
                write_evidence(evidence_path, evidence)
                print(json.dumps(asdict(evidence), ensure_ascii=False))
                return 2

            if args.dry_run:
                evidence.status = "passed"
                evidence.action = "would_fast_forward"
                evidence.target_sha_after = target_sha
                evidence.detail = "Fast-forward seguro validado; nenhuma alteração realizada por --dry-run."
                write_evidence(evidence_path, evidence)
                print(json.dumps(asdict(evidence), ensure_ascii=False))
                return 0

            run_git(
                ["push", args.gitlab_repository, f"{source_sha}:refs/heads/{args.target_branch}"],
                env=auth_env,
            )

            # Confirma o estado remoto após o push sem assumir sucesso apenas pelo exit code.
            run_git(
                ["fetch", "--no-tags", args.gitlab_repository, f"refs/heads/{args.target_branch}:{remote_ref}"],
                env=auth_env,
            )
            target_after = resolve_sha(remote_ref)
            if target_after != source_sha:
                raise SyncError(f"verificação pós-push falhou: GitLab={target_after}, GitHub={source_sha}")

            evidence.status = "passed"
            evidence.action = "fast_forward"
            evidence.target_sha_after = target_after
            evidence.detail = "GitLab atualizado por fast-forward e SHA remoto confirmado."
            write_evidence(evidence_path, evidence)
            print(json.dumps(asdict(evidence), ensure_ascii=False))
            return 0

    except Exception as exc:
        evidence.status = "failed"
        evidence.action = "none"
        evidence.detail = str(exc)
        write_evidence(evidence_path, evidence)
        print(json.dumps(asdict(evidence), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
