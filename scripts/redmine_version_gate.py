#!/usr/bin/env python3
"""Política fail-closed de versão suportada do Redmine para integrações ReqSys."""
from __future__ import annotations

import re
from dataclasses import dataclass

SUPPORTED_MINIMUMS: dict[tuple[int, int], tuple[int, int, int]] = {
    (6, 0): (6, 0, 11),
    (6, 1): (6, 1, 4),
    (7, 0): (7, 0, 1),
}

_VERSION_RE = re.compile(
    r"^\s*(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:[-+.\s].*)?\s*$"
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
    """Converte uma versão declarada, aceitando sufixos como '.stable'."""
    match = _VERSION_RE.fullmatch(value or "")
    if not match:
        raise RedmineVersionError(
            "Versão Redmine inválida; informe no formato MAJOR.MINOR.PATCH "
            "(ex.: 7.0.1)."
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
