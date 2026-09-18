#!/usr/bin/env python3
"""Atesta qual identidade GitLab responde pela credencial gerenciada do mirror.

Responde, sem expor o segredo, a pergunta que hoje bloqueia a Issue #1503:
qual das identidades homônimas `reqsys-github-mirror` é dona do token
armazenado no Azure Key Vault e o que exatamente falta autorizar nela.

Princípios:
- O token é lido somente de variável de ambiente; nunca é impresso, gravado
  em evidência nem enviado a terceiros.
- Somente leitura: nenhuma chamada altera identidade, permissão ou proteção
  de branch. A automação não eleva o próprio privilégio no GitLab.
- Fail-closed: com `--require-authorized`, sai diferente de zero enquanto a
  autorização humana mínima não estiver aplicada.
- Gera evidência JSON auditável com `correlation_id`.

Uso:
    GITLAB_MIRROR_TOKEN=... python scripts/attest_gitlab_mirror_identity.py
    GITLAB_MIRROR_TOKEN=... python scripts/attest_gitlab_mirror_identity.py --require-authorized
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

DEFAULT_API_BASE = "https://gitlab.com/api/v4"
DEFAULT_PROJECT_PATH = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_IDENTITY_NAME = "reqsys-github-mirror"
DEFAULT_TARGET_BRANCH = "main"
DEFAULT_CREDENTIAL_ID = "gitlab-main-mirror"
DEFAULT_SECRET_NAME = "reqsys-gitlab-main-mirror-token"
DEFAULT_EVIDENCE = "audit/gitlab-mirror-identity-attestation.json"

ACCESS_LEVEL_NAMES = {
    0: "no_one",
    5: "minimal",
    10: "guest",
    20: "reporter",
    30: "developer",
    40: "maintainer",
    50: "owner",
}

# Menor nível capaz de receber allowance de push em branch protegida no GitLab.
MINIMUM_PUSH_ACCESS_LEVEL = 30

VERDICT_AUTHORIZED = "authorized"
VERDICT_INSUFFICIENT = "insufficient_permission"
VERDICT_FORCE_PUSH_ENABLED = "force_push_enabled"
VERDICT_UNDETERMINED = "undetermined"
VERDICT_UNRESOLVED = "unresolved"


class AttestationError(RuntimeError):
    pass


class SecretLeakError(RuntimeError):
    """Levantado quando a evidência serializada conteria o segredo."""


@dataclass
class ApiResult:
    ok: bool
    status: int
    payload: Any = None
    error: str | None = None


@dataclass
class Identity:
    id: int | None
    username: str | None
    name: str | None
    state: str | None = None
    bot: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "state": self.state,
            "bot": self.bot,
        }


@dataclass
class Attestation:
    verdict: str
    findings: list[str] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def correlation_id() -> str:
    explicit = os.getenv("CORRELATION_ID", "").strip()
    if explicit:
        return explicit
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    attempt = os.getenv("GITHUB_RUN_ATTEMPT", "1")
    return f"gitlab-mirror-identity-{run_id}-{attempt}"


def access_level_name(level: int | None) -> str | None:
    if level is None:
        return None
    return ACCESS_LEVEL_NAMES.get(level, f"custom_{level}")


def make_fetch(api_base: str, token: str) -> Callable[[str], ApiResult]:
    """Constrói o leitor HTTP somente-leitura da API do GitLab."""

    def fetch(path: str) -> ApiResult:
        url = f"{api_base.rstrip('/')}/{path.lstrip('/')}"
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"PRIVATE-TOKEN": token, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                return ApiResult(ok=True, status=response.status, payload=json.loads(body or "null"))
        except urllib.error.HTTPError as exc:
            return ApiResult(ok=False, status=exc.code, error=f"HTTP {exc.code}")
        except urllib.error.URLError as exc:
            return ApiResult(ok=False, status=0, error=f"falha de rede: {exc.reason}")
        except json.JSONDecodeError:
            return ApiResult(ok=False, status=0, error="resposta não é JSON válido")

    return fetch


def read_identity(fetch: Callable[[str], ApiResult]) -> tuple[Identity | None, str | None]:
    result = fetch("/user")
    if not result.ok or not isinstance(result.payload, dict):
        return None, result.error or "identidade efetiva não pôde ser lida"
    payload = result.payload
    return (
        Identity(
            id=payload.get("id"),
            username=payload.get("username"),
            name=payload.get("name"),
            state=payload.get("state"),
            bot=payload.get("bot"),
        ),
        None,
    )


def read_token_metadata(fetch: Callable[[str], ApiResult]) -> dict[str, Any] | None:
    """Metadados do token (nunca o valor). Indisponível para alguns tipos de token."""
    result = fetch("/personal_access_tokens/self")
    if not result.ok or not isinstance(result.payload, dict):
        return None
    payload = result.payload
    return {
        "id": payload.get("id"),
        "name": payload.get("name"),
        "user_id": payload.get("user_id"),
        "scopes": payload.get("scopes"),
        "active": payload.get("active"),
        "revoked": payload.get("revoked"),
        "expires_at": payload.get("expires_at"),
        "last_used_at": payload.get("last_used_at"),
    }


def read_candidates(
    fetch: Callable[[str], ApiResult], project_id: str, identity_name: str
) -> list[dict[str, Any]] | None:
    """Enumera as identidades homônimas com acesso ao projeto."""
    query = urllib.parse.quote(identity_name, safe="")
    result = fetch(f"/projects/{project_id}/members/all?query={query}&per_page=100")
    if not result.ok or not isinstance(result.payload, list):
        return None
    needle = identity_name.casefold()
    candidates = []
    for member in result.payload:
        if not isinstance(member, dict):
            continue
        haystack = f"{member.get('username') or ''} {member.get('name') or ''}".casefold()
        if needle not in haystack:
            continue
        candidates.append(
            {
                "id": member.get("id"),
                "username": member.get("username"),
                "name": member.get("name"),
                "state": member.get("state"),
                "access_level": (member.get("access_level")),
                "access_level_name": access_level_name(member.get("access_level")),
            }
        )
    return candidates


def read_membership(
    fetch: Callable[[str], ApiResult], project_id: str, user_id: int
) -> dict[str, Any] | None:
    result = fetch(f"/projects/{project_id}/members/all/{user_id}")
    if not result.ok or not isinstance(result.payload, dict):
        return None
    payload = result.payload
    level = payload.get("access_level")
    return {
        "access_level": level,
        "access_level_name": access_level_name(level),
        "expires_at": payload.get("expires_at"),
        "membership_state": payload.get("membership_state"),
    }


def read_protected_branch(
    fetch: Callable[[str], ApiResult], project_id: str, branch: str
) -> dict[str, Any] | None:
    encoded = urllib.parse.quote(branch, safe="")
    result = fetch(f"/projects/{project_id}/protected_branches/{encoded}")
    if not result.ok or not isinstance(result.payload, dict):
        return None
    payload = result.payload
    return {
        "name": payload.get("name"),
        "allow_force_push": payload.get("allow_force_push"),
        "push_access_levels": payload.get("push_access_levels") or [],
        "merge_access_levels": payload.get("merge_access_levels") or [],
    }


def allowance_matches(
    entry: dict[str, Any], *, user_id: int | None, access_level: int | None
) -> bool:
    """Um allowance de branch protegida cobre a identidade informada?"""
    if not isinstance(entry, dict):
        return False
    if entry.get("user_id") is not None and entry.get("user_id") == user_id:
        return True
    required = entry.get("access_level")
    if required is None or access_level is None:
        return False
    if required < MINIMUM_PUSH_ACCESS_LEVEL:
        # `no_one` (0) e níveis abaixo de Developer não concedem push.
        return False
    return access_level >= required


def evaluate_push_allowance(
    protected_branch: dict[str, Any], *, user_id: int | None, access_level: int | None
) -> bool:
    return any(
        allowance_matches(entry, user_id=user_id, access_level=access_level)
        for entry in protected_branch.get("push_access_levels", [])
    )


def unevaluable_allowances(protected_branch: dict[str, Any]) -> list[dict[str, Any]]:
    """Allowances cuja cobertura não pode ser decidida só com identidade e nível.

    Concessões por grupo ou deploy key exigiriam consultar a composição do grupo
    ou a chave; sem isso, um veredito negativo pode ser falso negativo.
    """
    return [
        entry
        for entry in protected_branch.get("push_access_levels", [])
        if isinstance(entry, dict)
        and (entry.get("group_id") is not None or entry.get("deploy_key_id") is not None)
    ]


def classify_verdict(
    *,
    identity: Identity | None,
    membership: dict[str, Any] | None,
    protected_branch: dict[str, Any] | None,
    candidates: list[dict[str, Any]] | None,
    token_metadata: dict[str, Any] | None = None,
) -> Attestation:
    """Deriva o veredito de autorização a partir do estado observado."""
    findings: list[str] = []

    if identity is None or identity.id is None:
        findings.append(
            "A credencial do cofre não resolveu nenhuma identidade GitLab; "
            "verifique se o segredo está presente e ativo."
        )
        return Attestation(verdict=VERDICT_UNRESOLVED, findings=findings)

    if identity.state and identity.state != "active":
        findings.append(f"Identidade autoritativa não está ativa (state={identity.state}).")

    if token_metadata and token_metadata.get("revoked"):
        findings.append("O token do cofre está revogado no GitLab.")
    if token_metadata and token_metadata.get("active") is False:
        findings.append("O token do cofre está inativo no GitLab.")
    if (
        token_metadata
        and token_metadata.get("user_id") is not None
        and token_metadata.get("user_id") != identity.id
    ):
        findings.append(
            "Divergência entre o dono do token e a identidade efetiva "
            f"(token.user_id={token_metadata.get('user_id')}, identidade={identity.id})."
        )

    homonimas = [c for c in (candidates or []) if c.get("id") != identity.id]
    for outra in homonimas:
        findings.append(
            "Identidade homônima não autoritativa presente no projeto: "
            f"id={outra.get('id')} username={outra.get('username')} "
            f"acesso={outra.get('access_level_name')}. Avaliar desativação após a correlação."
        )

    access_level = (membership or {}).get("access_level")
    if membership is None:
        findings.append(
            "Não foi possível ler a associação da identidade no projeto com o privilégio atual."
        )

    if protected_branch is None:
        findings.append(
            "Configuração da branch protegida não é legível com o privilégio atual; "
            "a autorização não pode ser confirmada automaticamente."
        )
        return Attestation(verdict=VERDICT_UNDETERMINED, findings=findings)

    can_push = evaluate_push_allowance(
        protected_branch, user_id=identity.id, access_level=access_level
    )
    if not can_push:
        findings.append(
            "A identidade autoritativa não consta nos allowances de push da branch protegida "
            f"`{protected_branch.get('name')}`; o mirror permanece bloqueado."
        )
        for entry in unevaluable_allowances(protected_branch):
            findings.append(
                "Allowance de push concedido a grupo/deploy key "
                f"(group_id={entry.get('group_id')}, deploy_key_id={entry.get('deploy_key_id')}) "
                "não é avaliável automaticamente; confirmar manualmente se cobre a identidade "
                "antes de conceder acesso adicional."
            )
        return Attestation(verdict=VERDICT_INSUFFICIENT, findings=findings)

    if protected_branch.get("allow_force_push"):
        findings.append(
            "A branch protegida está com `allow_force_push` habilitado, o que viola o "
            "critério de conclusão (force-push deve permanecer proibido)."
        )
        return Attestation(verdict=VERDICT_FORCE_PUSH_ENABLED, findings=findings)

    findings.append(
        "Identidade autoritativa autorizada a avançar a branch protegida por fast-forward, "
        "com force-push proibido."
    )
    return Attestation(verdict=VERDICT_AUTHORIZED, findings=findings)


def render_human_action(
    *, identity: Identity | None, credential_id: str, target_branch: str
) -> dict[str, Any] | None:
    """Ação humana mínima restante, já parametrizada com a identidade resolvida."""
    if identity is None or identity.id is None:
        return {
            "statement": None,
            "blocked_by": "identidade não resolvida",
            "steps": [
                "Confirmar que o segredo do Key Vault está presente, ativo e não revogado.",
                "Reexecutar esta atestação para obter a identidade autoritativa.",
            ],
        }
    statement = (
        f"AUTORIZO a identidade técnica {identity.username} (GitLab user id {identity.id}), "
        f"vinculada à credencial gerenciada `{credential_id}` do Key Vault, a realizar somente "
        f"fast-forward na branch protegida `{target_branch}` do GitLab, mantendo force-push proibido."
    )
    return {
        "statement": statement,
        "blocked_by": "concessão de permissão no GitLab (não automatizável pela automação)",
        "steps": [
            f"Em Settings > Repository > Protected branches, na branch `{target_branch}`, "
            f"incluir o usuário id {identity.id} ({identity.username}) em "
            "'Allowed to push and merge'.",
            "Manter 'Allow force push' desabilitado.",
            "Não desproteger a branch nem elevar o nível de acesso além do necessário.",
            "Reexecutar esta atestação com --require-authorized para confirmar o estado.",
        ],
    }


def build_evidence(
    *,
    project_path: str,
    target_branch: str,
    identity_name: str,
    credential_id: str,
    secret_name: str,
    identity: Identity | None,
    identity_error: str | None,
    token_metadata: dict[str, Any] | None,
    candidates: list[dict[str, Any]] | None,
    membership: dict[str, Any] | None,
    protected_branch: dict[str, Any] | None,
    attestation: Attestation,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "timestamp_utc": utc_now(),
        "correlation_id": correlation_id(),
        "contract": "reqsys-gitlab-mirror-identity-attestation",
        "read_only": True,
        "verdict": attestation.verdict,
        "findings": attestation.findings,
        "project_path": project_path,
        "target_branch": target_branch,
        "identity_name_queried": identity_name,
        "credential": {
            "credential_id": credential_id,
            "secret_name": secret_name,
            "source": "azure_key_vault",
            "secret_value_disclosed": False,
        },
        "authoritative_identity": identity.as_dict() if identity else None,
        "identity_error": identity_error,
        "token_metadata": token_metadata,
        "homonymous_candidates": candidates,
        "project_membership": membership,
        "protected_branch": protected_branch,
        "remaining_human_action": (
            None
            if attestation.verdict == VERDICT_AUTHORIZED
            else render_human_action(
                identity=identity, credential_id=credential_id, target_branch=target_branch
            )
        ),
    }


def assert_no_secret(serialized: str, token: str) -> None:
    if token and token in serialized:
        raise SecretLeakError("evidência conteria o valor do token; gravação abortada")


def write_evidence(path: Path, evidence: dict[str, Any], token: str) -> str:
    serialized = json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    assert_no_secret(serialized, token)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")
    return serialized


def collect(
    fetch: Callable[[str], ApiResult],
    *,
    project_path: str,
    identity_name: str,
    target_branch: str,
) -> dict[str, Any]:
    """Coleta somente-leitura de todo o estado necessário à atestação."""
    project_id = urllib.parse.quote(project_path, safe="")
    identity, identity_error = read_identity(fetch)
    token_metadata = read_token_metadata(fetch)
    candidates = read_candidates(fetch, project_id, identity_name)
    membership = (
        read_membership(fetch, project_id, identity.id)
        if identity and identity.id is not None
        else None
    )
    protected_branch = read_protected_branch(fetch, project_id, target_branch)
    return {
        "identity": identity,
        "identity_error": identity_error,
        "token_metadata": token_metadata,
        "candidates": candidates,
        "membership": membership,
        "protected_branch": protected_branch,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=os.getenv("GITLAB_API_BASE", DEFAULT_API_BASE))
    parser.add_argument("--project-path", default=DEFAULT_PROJECT_PATH)
    parser.add_argument("--identity-name", default=DEFAULT_IDENTITY_NAME)
    parser.add_argument("--target-branch", default=DEFAULT_TARGET_BRANCH)
    parser.add_argument("--credential-id", default=DEFAULT_CREDENTIAL_ID)
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    parser.add_argument("--token-env", default="GITLAB_MIRROR_TOKEN")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE)
    parser.add_argument(
        "--require-authorized",
        action="store_true",
        help="sai com código 2 enquanto a autorização humana mínima não estiver aplicada",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    evidence_path = Path(args.evidence)
    token = os.getenv(args.token_env, "").strip()

    if not token:
        attestation = Attestation(
            verdict=VERDICT_UNRESOLVED,
            findings=[f"variável protegida {args.token_env} não configurada"],
        )
        evidence = build_evidence(
            project_path=args.project_path,
            target_branch=args.target_branch,
            identity_name=args.identity_name,
            credential_id=args.credential_id,
            secret_name=args.secret_name,
            identity=None,
            identity_error=f"{args.token_env} ausente",
            token_metadata=None,
            candidates=None,
            membership=None,
            protected_branch=None,
            attestation=attestation,
        )
        print(write_evidence(evidence_path, evidence, token), end="")
        return 1

    collected = collect(
        make_fetch(args.api_base, token),
        project_path=args.project_path,
        identity_name=args.identity_name,
        target_branch=args.target_branch,
    )
    attestation = classify_verdict(
        identity=collected["identity"],
        membership=collected["membership"],
        protected_branch=collected["protected_branch"],
        candidates=collected["candidates"],
        token_metadata=collected["token_metadata"],
    )
    evidence = build_evidence(
        project_path=args.project_path,
        target_branch=args.target_branch,
        identity_name=args.identity_name,
        credential_id=args.credential_id,
        secret_name=args.secret_name,
        identity=collected["identity"],
        identity_error=collected["identity_error"],
        token_metadata=collected["token_metadata"],
        candidates=collected["candidates"],
        membership=collected["membership"],
        protected_branch=collected["protected_branch"],
        attestation=attestation,
    )
    print(write_evidence(evidence_path, evidence, token), end="")

    if attestation.verdict == VERDICT_AUTHORIZED:
        return 0
    if args.require_authorized:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
