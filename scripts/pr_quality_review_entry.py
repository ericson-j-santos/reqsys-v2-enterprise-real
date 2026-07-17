#!/usr/bin/env python3
"""Entry point governado do PR Quality Review.

Corrige a classificação de arquivos sensíveis sem alterar a API do analisador
legado. Arquivos de código ou documentação cujo nome contém palavras como
``secret`` ou ``token`` não são segredos por si só. O bloqueio crítico deve
ocorrer apenas para artefatos com formato e nome compatíveis com material
sensível real.
"""
from __future__ import annotations

from pathlib import Path

import pr_quality_review as review

_SAFE_CODE_AND_DOC_EXTENSIONS = {
    ".c",
    ".cpp",
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".md",
    ".mdx",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
}
_SENSITIVE_EXTENSIONS = {".key", ".p12", ".pfx", ".pem"}
_SENSITIVE_CONFIG_EXTENSIONS = {"", ".conf", ".ini", ".json", ".toml", ".yaml", ".yml"}
_EXACT_SENSITIVE_NAMES = {
    "credentials",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "service-account.json",
    "service_account.json",
}
_SENSITIVE_MARKERS = ("credential", "private_key", "secret", "token")
_SAFE_PUBLIC_ARTIFACTS = {
    "frontend/artifacts/figma-tokens/drift-report.json",
    "frontend/artifacts/figma-tokens/manifest.json",
    "frontend/artifacts/figma-tokens/reqsys.tokens.json",
    "frontend/artifacts/figma-tokens/reqsys.tokens.sha256",
}


def _is_sensitive(self: review.ChangedFile) -> bool:
    lowered = self.filename.lower()
    name = Path(lowered).name
    suffix = Path(name).suffix.lower()

    if lowered in _SAFE_PUBLIC_ARTIFACTS:
        return False
    if any(lowered.endswith(template_suffix) for template_suffix in review.SAFE_TEMPLATE_SUFFIXES):
        return False
    if name == ".env" or name.startswith(".env."):
        return True
    if name in _EXACT_SENSITIVE_NAMES or suffix in _SENSITIVE_EXTENSIONS:
        return True
    if suffix in _SAFE_CODE_AND_DOC_EXTENSIONS:
        return False
    return suffix in _SENSITIVE_CONFIG_EXTENSIONS and any(marker in name for marker in _SENSITIVE_MARKERS)


review.ChangedFile.is_sensitive = property(_is_sensitive)


if __name__ == "__main__":
    raise SystemExit(review.main())
