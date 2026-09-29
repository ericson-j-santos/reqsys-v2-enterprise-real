#!/usr/bin/env python3
"""Monitor de desvios materiais de governança do repositório ReqSys."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MARKER = "<!-- reqsys-governance-drift-monitor -->"
DEFAULT_RULESET_REF = "~DEFAULT_BRANCH"

CONTROL_FILES: dict[str, tuple[str, str]] = {
    "ci_removed": (".github/workflows/ci.yml", "CI — ReqSys v2 Enterprise"),
    "governance_removed": (
        ".github/workflows/governance-quality-gates.yml",
        "Governance Quality Gates",
    ),
    # "Settings Hardening Evidence" é o nome lógico pedido para o controle.
    # O equivalente versionado atual do ReqSys é o Branch Protection Audit.
    "settings_hardening_evidence_removed": (
        ".github/workflows/branch-protection-audit.yml",
        "Branch Protection Audit",
    ),
    "pr_evidence_gate_removed": (
        ".github/workflows/pr-evidence-gate.yml",
        "PR Evidence Gate",
    ),
}

DRIFT_METADATA: dict[str, dict[str, str]] = {
    "ci_removed": {
        "impact": "O gate canônico de CI deixa de materializar a evidência principal de qualidade.",
        "risk": "alto",
        "correction": "Restaurar o workflow CI canônico no mesmo caminho/nome e revalidar o HEAD atual.",
    },
    "governance_removed": {
        "impact": "O gate de governança deixa de validar políticas antes do merge.",
        "risk": "alto",
        "correction": "Restaurar Governance Quality Gates e revalidar seus checks no HEAD atual.",
    },
    "settings_hardening_evidence_removed": {
        "impact": "A evidência versionada de hardening das configurações deixa de ser produzida.",
        "risk": "alto",
        "correction": "Restaurar Branch Protection Audit (equivalente atual de Settings Hardening Evidence) e reexecutar a auditoria.",
    },
    "pr_evidence_gate_removed": {
        "impact": "A PR pode perder a verificação explícita de evidência vinculada ao HEAD atual.",
        "risk": "alto",
        "correction": "Restaurar PR Evidence Gate e revalidar a evidência no SHA corrente.",
    },
    "admin_protection_altered": {
        "impact": "Administradores ou atores de bypass podem contornar a proteção da branch padrão.",
        "risk": "alto",
        "correction": "Remover bypass actors do ruleset ativo da branch padrão e confirmar por leitura independente.",
    },
    "force_push_enabled": {
        "impact": "O histórico da branch padrão pode ser reescrito por non-fast-forward.",
        "risk": "alto",
        "correction": "Restaurar a regra non_fast_forward no ruleset ativo da branch padrão e confirmar por leitura independente.",
    },
    "deletion_enabled": {
        "impact": "A branch padrão pode ser excluída.",
        "risk": "alto",
        "correction": "Restaurar a regra deletion no ruleset ativo da branch padrão e confirmar por leitura independente.",
    },
    "auto_merge_disabled": {
        "impact": "O fluxo CI-driven deixa de poder concluir PRs elegíveis pelo mecanismo nativo governado.",
        "risk": "médio",
        "correction": "Reabilitar allow_auto_merge no repositório sem reduzir checks, revisão ou merge queue.",
    },
    "expected_head_sha_weakened": {
        "impact": "Uma decisão de merge pode ser reaproveitada depois de mudança do HEAD, criando risco de corrida com evidência obsoleta.",
        "risk": "alto",
        "correction": "Restaurar releitura imediata do HEAD e enviar o SHA esperado na chamada de merge; revalidar com teste de mudança concorrente.",
    },
}


class CollectionError(RuntimeError):
    """Falha de coleta que impede afirmar drift material."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _github_get(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "reqsys-governance-drift-monitor",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise CollectionError(f"github_api_read_failed:{url}:{exc}") from exc


def collect_live_state(repository: str, token: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base = f"https://api.github.com/repos/{repository}"
    repository_payload = _github_get(base, token)
    summaries = _github_get(f"{base}/rulesets?per_page=100", token)
    if not isinstance(summaries, list):
        raise CollectionError("ruleset_collection_invalid")
    if len(summaries) >= 100:
        raise CollectionError("ruleset_collection_may_be_incomplete")

    details: list[dict[str, Any]] = []
    for item in summaries:
        ruleset_id = item.get("id")
        if ruleset_id is None:
            raise CollectionError("ruleset_id_missing")
        details.append(_github_get(f"{base}/rulesets/{ruleset_id}", token))
    return repository_payload, details


def _workflow_ok(root: Path, path: str, expected_name: str) -> tuple[bool, dict[str, Any]]:
    file_path = root / path
    if not file_path.is_file():
        return False, {"path": path, "present": False, "expected_name": expected_name}
    text = file_path.read_text(encoding="utf-8")
    pattern = re.compile(rf"(?m)^name:\s*['\"]?{re.escape(expected_name)}['\"]?\s*$")
    name_matches = bool(pattern.search(text))
    return name_matches, {
        "path": path,
        "present": True,
        "expected_name": expected_name,
        "name_matches": name_matches,
    }


def _default_branch_rulesets(rulesets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for ruleset in rulesets:
        if ruleset.get("target") != "branch" or ruleset.get("enforcement") != "active":
            continue
        ref_name = ((ruleset.get("conditions") or {}).get("ref_name") or {})
        includes = set(ref_name.get("include") or [])
        if DEFAULT_RULESET_REF in includes:
            selected.append(ruleset)
    return selected


def _merge_sha_contract(root: Path) -> tuple[bool, dict[str, Any]]:
    path = ".github/workflows/governed-pr-automation.yml"
    file_path = root / path
    if not file_path.is_file():
        return False, {"path": path, "present": False, "required_markers": []}

    text = file_path.read_text(encoding="utf-8")
    markers = {
        "capture_trigger_head": "const triggerHeadSha = context.payload.workflow_run.head_sha;" in text,
        "initial_head_compare": "pr.head.sha !== triggerHeadSha" in text,
        "pre_merge_head_compare": "current.head.sha !== triggerHeadSha" in text,
        "merge_uses_expected_sha": bool(re.search(r"(?m)^\s*sha:\s*triggerHeadSha,?\s*$", text)),
    }
    return all(markers.values()), {
        "path": path,
        "present": True,
        "required_markers": markers,
        "contract": "releitura do HEAD + sha esperado na mutação de merge",
    }


def _drift(kind: str, evidence: dict[str, Any]) -> dict[str, Any]:
    metadata = DRIFT_METADATA[kind]
    return {
        "kind": kind,
        "impact": metadata["impact"],
        "risk": metadata["risk"],
        "correction": metadata["correction"],
        "evidence": evidence,
    }


def analyze(
    repository_payload: dict[str, Any],
    rulesets: list[dict[str, Any]],
    *,
    root: Path,
    source_sha: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    drifts: list[dict[str, Any]] = []
    controls: dict[str, Any] = {}

    for kind, (path, expected_name) in CONTROL_FILES.items():
        ok, evidence = _workflow_ok(root, path, expected_name)
        controls[kind] = evidence
        if not ok:
            drifts.append(_drift(kind, evidence))

    active_rulesets = _default_branch_rulesets(rulesets)
    rule_types = {
        str(rule.get("type"))
        for ruleset in active_rulesets
        for rule in (ruleset.get("rules") or [])
        if rule.get("type")
    }
    bypass_actors = [
        actor
        for ruleset in active_rulesets
        for actor in (ruleset.get("bypass_actors") or [])
    ]
    ruleset_evidence = {
        "active_default_branch_ruleset_ids": [item.get("id") for item in active_rulesets],
        "rule_types": sorted(rule_types),
        "bypass_actor_count": len(bypass_actors),
    }
    controls["ruleset"] = ruleset_evidence

    if not active_rulesets or bypass_actors:
        drifts.append(_drift("admin_protection_altered", ruleset_evidence))
    if "non_fast_forward" not in rule_types:
        drifts.append(_drift("force_push_enabled", ruleset_evidence))
    if "deletion" not in rule_types:
        drifts.append(_drift("deletion_enabled", ruleset_evidence))

    auto_merge_enabled = repository_payload.get("allow_auto_merge") is True
    controls["auto_merge"] = {
        "allow_auto_merge": repository_payload.get("allow_auto_merge"),
    }
    if not auto_merge_enabled:
        drifts.append(_drift("auto_merge_disabled", controls["auto_merge"]))

    merge_contract_ok, merge_contract_evidence = _merge_sha_contract(root)
    controls["expected_head_sha"] = merge_contract_evidence
    if not merge_contract_ok:
        drifts.append(_drift("expected_head_sha_weakened", merge_contract_evidence))

    active = sorted(item["kind"] for item in drifts)
    return {
        "schema_version": "1",
        "generated_at": generated_at or _now_iso(),
        "repository": repository_payload.get("full_name"),
        "source_sha": source_sha,
        "material_drift": bool(drifts),
        "active_drifts": active,
        "controls": controls,
        "drifts": drifts,
        "mappings": {
            "Settings Hardening Evidence": {
                "workflow": "Branch Protection Audit",
                "path": ".github/workflows/branch-protection-audit.yml",
                "reason": "equivalente versionado atual que audita hardening/proteção da branch",
            }
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        MARKER,
        "# ReqSys — monitor de governança",
        "",
        f"- Estado: **{'DESVIO MATERIAL' if report['material_drift'] else 'sem desvio material'}**",
        f"- Repositório: `{report.get('repository') or 'desconhecido'}`",
        f"- SHA observado: `{report['source_sha']}`",
        f"- Coleta: `{report['generated_at']}`",
        "- Settings Hardening Evidence: mapeado para `Branch Protection Audit`.",
        "",
    ]
    if not report["drifts"]:
        lines.append("Nenhum dos desvios materiais configurados foi detectado.")
        lines.append("")
        return "\n".join(lines)

    for item in report["drifts"]:
        lines.extend(
            [
                f"## {item['kind']}",
                "",
                f"- Evidência atual: `{json.dumps(item['evidence'], ensure_ascii=False, sort_keys=True)}`",
                f"- Impacto: {item['impact']}",
                f"- Risco: **{item['risk']}**",
                f"- Menor correção segura e idempotente: {item['correction']}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    repository = os.environ.get("REPOSITORY") or os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    source_sha = os.environ.get("EVALUATED_SHA") or os.environ.get("GITHUB_SHA", "")
    if not repository or "/" not in repository:
        raise SystemExit("REPOSITORY_INVALID")
    if not token:
        raise SystemExit("GITHUB_TOKEN_MISSING")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise SystemExit("EVALUATED_SHA_INVALID")

    repository_payload, rulesets = collect_live_state(repository, token)
    report = analyze(
        repository_payload,
        rulesets,
        root=Path.cwd(),
        source_sha=source_sha,
    )

    out_dir = Path("audit/governance-drift-monitor")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")

    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(
                "material_drift="
                + ("true" if report["material_drift"] else "false")
                + "\n"
            )
            handle.write("active_drifts=" + ",".join(report["active_drifts"]) + "\n")

    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CollectionError as exc:
        print(f"GOVERNANCE_MONITOR_COLLECTION_FAILED:{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
