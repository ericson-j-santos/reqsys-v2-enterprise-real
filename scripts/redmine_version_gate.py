#!/usr/bin/env python3
"""Política fail-closed de versão suportada do Redmine para integrações ReqSys."""
from __future__ import annotations

import re
from dataclasses import dataclass

# Security Advisories revalidado em 2026-10-18: #44467 e #44468.
# 6.0 permanece mantida upstream, mas não possui correção homologada desses
# avisos. Não confundir bloqueio de integração com fim de suporte (EOL).
# Fonte: https://www.redmine.org/projects/redmine/wiki/Security_Advisories
SUPPORTED_MINIMUMS: dict[tuple[int, int], tuple[int, int, int]] = {
    (6, 1): (6, 1, 5),
    (7, 0): (7, 0, 2),
}
SERIES_WITHOUT_SECURITY_FIX = frozenset({(6, 0)})

_VERSION_RE = re.compile(
    r"^\s*(?P<major>[0-9]+)\.(?P<minor>[0-9]+)\.(?P<patch>[0-9]+)"
    r"(?:\.stable(?:\.[0-9]+)?)?\s*$"
)


class RedmineVersionError(ValueError):
    """Versão ausente ou em formato que não pode ser avaliado com segurança."""


@dataclass(frozen=True)
class RedmineVersionDecision:
    status: str
    reason: str
    version: tuple[int, int, int]
    minimum: tuple[int, int, int] | None

    @property
    def allowed(self) -> bool:
        return self.status == "passed"


def parse_redmine_version(value: str) -> tuple[int, int, int]:
    """Aceita release ou '.stable[.revisão]'; rejeita versões de desenvolvimento."""
    match = _VERSION_RE.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise RedmineVersionError(
            "Versão Redmine inválida; informe no formato MAJOR.MINOR.PATCH "
            "(ex.: 6.1.5); somente release ou sufixo .stable[.revisão]."
        )
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


def evaluate_redmine_version(value: str) -> RedmineVersionDecision:
    """Avalia a versão declarada contra a baseline de segurança homologada."""
    version = parse_redmine_version(value)
    major, minor, _patch = version

    if major <= 5:
        return RedmineVersionDecision(
            status="blocked",
            reason="redmine_version_eol",
            version=version,
            minimum=None,
        )

    if (major, minor) in SERIES_WITHOUT_SECURITY_FIX:
        return RedmineVersionDecision(
            status="blocked",
            reason="redmine_version_sem_correcao_homologada",
            version=version,
            minimum=None,
        )

    minimum = SUPPORTED_MINIMUMS.get((major, minor))
    if minimum is None:
        return RedmineVersionDecision(
            status="blocked",
            reason="redmine_version_nao_homologada",
            version=version,
            minimum=None,
        )

    if version < minimum:
        return RedmineVersionDecision(
            status="blocked",
            reason="redmine_version_vulneravel",
            version=version,
            minimum=minimum,
        )

    return RedmineVersionDecision(
        status="passed",
        reason="redmine_version_suportada",
        version=version,
        minimum=minimum,
    )


def format_version(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)
