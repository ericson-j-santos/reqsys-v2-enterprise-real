"""Escopo de permissoes do GITHUB_TOKEN para os workflows criticos do ReqSys.

Analisa a estrutura YAML em vez de buscar tokens no texto:
"contents: write" no corpo de um script ou comentario nao e uma permissao.
Qualquer elevacao nao declarada falha fechada, inclusive write-all.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import yaml

# Excecao explicita: esse workflow tem apenas um job e precisa comentar o PR.
ALLOWED_ROOT_WRITES: dict[str, frozenset[str]] = {
    ".github/workflows/pr-conflict-guard.yml": frozenset({"issues"}),
}

# Permissoes elevadas exclusivamente nos jobs que realmente efetuam a operacao.
# structural-queue: atualizar branch e registrar diagnostico.
# manual-watch: comentar o diagnostico quando solicitado.
# remediate-workflow-run: rerun-failed-jobs sob politicas de remediacao.
# sweep-open-prs: remediacao e comentario de evidencias.
ALLOWED_JOB_WRITES: dict[str, dict[str, frozenset[str]]] = {
    ".github/workflows/pr-ci-watch.yml": {
        "structural-queue": frozenset({"contents", "issues", "pull-requests"}),
        "manual-watch": frozenset({"issues"}),
        "remediate-workflow-run": frozenset({"actions"}),
        "sweep-open-prs": frozenset({"actions", "issues"}),
    },
}

PERMISSION_VALUES = frozenset({"read", "write", "none"})


class _StrictWorkflowLoader(yaml.BaseLoader):
    """All keys remain text; duplicates fail closed instead of last-key-wins."""


def _unique_mapping(loader: _StrictWorkflowLoader, node: yaml.MappingNode) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in result:
            raise yaml.constructor.ConstructorError(
                "invalid workflow mapping",
                node.start_mark,
                "duplicate_or_nonscalar_mapping_key",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_StrictWorkflowLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _unique_mapping,
)

KNOWN_SCOPES = frozenset({
    "actions", "attestations", "checks", "contents", "deployments",
    "discussions", "id-token", "issues", "models", "packages",
    "pages", "pull-requests", "repository-projects",
    "security-events", "statuses",
})



def _parse_permissions(value: Any, *, location: str) -> tuple[set[str], list[str]]:
    if isinstance(value, str):
        if value == "read-all":
            return set(), []
        return set(), [f"{location}: permission_scalar_not_allowed"]
    if not isinstance(value, Mapping):
        return set(), [f"{location}: permission_map_required"]

    writes: set[str] = set()
    errors: list[str] = []
    for key, level in value.items():
        if not isinstance(key, str) or key not in KNOWN_SCOPES:
            errors.append(f"{location}: invalid_permission_scope")
            continue
        if not isinstance(level, str) or level not in PERMISSION_VALUES:
            errors.append(f"{location}:{key}: invalid_permission_level")
            continue
        if level == "write":
            writes.add(key)
    return writes, errors


def audit_permissions(source: str, path: str) -> dict[str, list[str]]:
    """Validar ausencia de elevacao inesperada por escopo/job, sem rede/escrita."""
    allowed_root = ALLOWED_ROOT_WRITES.get(path, frozenset())
    allowed_jobs = ALLOWED_JOB_WRITES.get(path, {})
    allowed = [
        *[f"workflow:{scope}: write" for scope in sorted(allowed_root)],
        *[
            f"{job}:{scope}: write"
            for job, scopes in sorted(allowed_jobs.items())
            for scope in sorted(scopes)
        ],
    ]
    observed: list[str] = []
    failures: list[str] = []
    try:
        document = yaml.load(source, Loader=_StrictWorkflowLoader)
    except yaml.YAMLError:
        return {
            "allowed": allowed,
            "observed": observed,
            "violations": ["workflow_yaml_invalid"],
        }

    if not isinstance(document, Mapping):
        return {
            "allowed": allowed,
            "observed": observed,
            "violations": ["workflow_map_required"],
        }

    if "permissions" not in document:
        failures.append("workflow_permissions_missing")
    else:
        root_writes, errors = _parse_permissions(
            document["permissions"], location="workflow"
        )
        failures.extend(errors)
        observed.extend(
            f"workflow:{scope}: write" for scope in sorted(root_writes)
        )
        failures.extend(
            f"workflow:{scope}: unexpected_elevated_permission"
            for scope in sorted(root_writes - allowed_root)
        )

    jobs = document.get("jobs")
    if not isinstance(jobs, Mapping) or not jobs:
        failures.append("jobs_map_required")
    else:
        for job_name, job in jobs.items():
            if not isinstance(job_name, str) or not isinstance(job, Mapping):
                failures.append("invalid_job_contract")
                continue
            if "permissions" not in job:
                continue
            job_writes, errors = _parse_permissions(
                job["permissions"], location=job_name
            )
            failures.extend(errors)
            observed.extend(
                f"{job_name}:{scope}: write" for scope in sorted(job_writes)
            )
            failures.extend(
                f"{job_name}:{scope}: unexpected_elevated_permission"
                for scope in sorted(
                    job_writes - allowed_jobs.get(job_name, frozenset())
                )
            )
    return {
        "allowed": allowed,
        "observed": sorted(observed),
        "violations": sorted(set(failures)),
    }
