#!/usr/bin/env python3
"""Auditoria estática e operacional dos GitHub Actions do ReqSys.

Gera inventário JSON/CSV/Markdown com gatilhos, dependências, permissões,
segredos referenciados, artefatos, sinais de evidência/comentários, deploy,
último uso observado e recomendação conservadora de consolidação.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

WORKFLOW_DIR = Path(".github/workflows")
DEFAULT_OUTPUT_DIR = Path("artifacts/workflow-inventory-audit")
TOP_LEVEL_RE = re.compile(r"^[A-Za-z0-9_.-]+:\s*(?:#.*)?$")
SECRET_PATTERNS = (
    re.compile(r"\bsecrets\.([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"\bsecrets\[['\"]([^'\"]+)['\"]\]"),
)
LOCAL_WORKFLOW_USE_RE = re.compile(r"uses:\s*\.?/?\.github/workflows/([^\s#]+)")
WORKFLOW_RUN_INLINE_RE = re.compile(r"workflows:\s*\[([^\]]+)\]")

EVIDENCE_PATTERNS = (
    "actions/upload-artifact",
    "github_step_summary",
    "gh pr comment",
    "/issues/comments",
    "pull-requests: write",
    "issues: write",
)
DEPLOY_PATTERNS = (
    "flyctl ",
    "fly deploy",
    "kubectl ",
    "helm ",
    "az webapp",
    "azure/webapps-deploy",
    "docker push",
    "environment: production",
    "environment: prod",
)
SUPPORT_KEYWORDS = {
    "diagnostic", "diagnostico", "diagnóstico", "audit", "auditoria", "report",
    "relatorio", "relatório", "evidence", "evidencia", "evidência", "watch",
    "monitor", "dashboard", "operator", "rerun", "dispatcher", "smoke",
}
CORE_KEYWORDS = {
    "ci", "security", "seguranca", "segurança", "deploy", "release", "backup",
    "restore", "auth", "database", "migration", "runtime", "contract", "quality",
}
NOISE_TOKENS = {
    "reqsys", "workflow", "workflows", "github", "actions", "action", "v2",
    "enterprise", "main", "dev", "stg", "prod", "governed", "governance",
    "governanca", "padrao", "ouro", "auto", "operational", "ops",
}


@dataclass
class WorkflowRecord:
    path: str
    name: str
    triggers: list[str]
    callers: list[str]
    calls: list[str]
    permissions: list[str]
    secrets: list[str]
    artifacts: list[str]
    writes_comments_or_evidence: bool
    participates_in_deploy: bool
    last_use_observed_at: str | None
    last_use_run_url: str | None
    recent_run_count_in_sample: int
    duplication_group: str | None
    recommendation: str
    confidence: str
    requires_human_validation: bool
    rationale: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_workflows(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.glob("*.y*ml")):
        result[path.as_posix()] = path.read_text(encoding="utf-8")
    return result


def top_level_block(text: str, key: str) -> list[str]:
    lines = text.splitlines()
    start = None
    prefix = f"{key}:"
    for index, line in enumerate(lines):
        if line.startswith(prefix) and not line.startswith((" ", "\t")):
            start = index
            inline = line[len(prefix):].strip()
            if inline:
                return [inline]
            break
    if start is None:
        return []
    block: list[str] = []
    for line in lines[start + 1:]:
        if line and not line.startswith((" ", "\t")) and TOP_LEVEL_RE.match(line):
            break
        block.append(line)
    return block


def parse_name(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("name:"):
            value = line.split(":", 1)[1].strip().strip('"\'')
            return value or fallback
    return fallback


def parse_triggers(text: str) -> list[str]:
    for line in text.splitlines():
        if line.startswith("on:"):
            inline = line.split(":", 1)[1].strip()
            if inline:
                if inline.startswith("[") and inline.endswith("]"):
                    return sorted({x.strip().strip('"\'') for x in inline[1:-1].split(",") if x.strip()})
                return [inline.strip('"\'')]
            break
    block = top_level_block(text, "on")
    triggers: set[str] = set()
    for line in block:
        if not line.startswith("  ") or line.startswith("    "):
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+):?", stripped)
        if match:
            triggers.add(match.group(1))
    return sorted(triggers)


def parse_permissions(text: str) -> list[str]:
    for line in text.splitlines():
        if line.startswith("permissions:"):
            inline = line.split(":", 1)[1].strip()
            if inline:
                return [inline]
            break
    block = top_level_block(text, "permissions")
    values: list[str] = []
    for line in block:
        if line.startswith("  ") and not line.startswith("    ") and ":" in line:
            key, value = line.strip().split(":", 1)
            values.append(f"{key}:{value.strip()}")
    return sorted(values)


def parse_secrets(text: str) -> list[str]:
    found: set[str] = set()
    for pattern in SECRET_PATTERNS:
        found.update(pattern.findall(text))
    return sorted(found)


def parse_artifacts(text: str) -> list[str]:
    lines = text.splitlines()
    artifacts: list[str] = []
    for index, line in enumerate(lines):
        if "actions/upload-artifact" not in line.lower():
            continue
        for candidate in lines[index + 1:index + 15]:
            stripped = candidate.strip()
            if stripped.startswith("- name:") or "uses:" in stripped:
                break
            if stripped.startswith("name:"):
                value = stripped.split(":", 1)[1].strip().strip('"\'')
                if value:
                    artifacts.append(value)
                break
    return sorted(set(artifacts))


def parse_calls(text: str) -> tuple[set[str], set[str]]:
    path_calls = {f".github/workflows/{match}" for match in LOCAL_WORKFLOW_USE_RE.findall(text)}
    name_calls: set[str] = set()
    inline = WORKFLOW_RUN_INLINE_RE.search(text)
    if inline:
        for item in inline.group(1).split(","):
            value = item.strip().strip('"\'')
            if value:
                name_calls.add(value)
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "workflows:":
            base_indent = len(line) - len(line.lstrip())
            for candidate in lines[index + 1:]:
                indent = len(candidate) - len(candidate.lstrip())
                stripped = candidate.strip()
                if stripped and indent <= base_indent:
                    break
                if stripped.startswith("-"):
                    value = stripped[1:].strip().strip('"\'')
                    if value:
                        name_calls.add(value)
    return path_calls, name_calls


def normalized_cluster(path: str, name: str) -> str:
    raw = f"{Path(path).stem} {name}".lower()
    raw = (raw.replace("ç", "c").replace("ã", "a").replace("á", "a")
               .replace("é", "e").replace("í", "i").replace("ó", "o")
               .replace("ú", "u"))
    tokens = [token for token in re.findall(r"[a-z0-9]+", raw) if token not in NOISE_TOKENS and len(token) > 2]
    return "-".join(sorted(set(tokens))[:8]) or Path(path).stem.lower()


def github_get(url: str, token: str) -> dict[str, Any]:
    request = Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - URL GitHub controlada.
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API HTTP {exc.code}: {body[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API indisponível: {exc}") from exc


def fetch_recent_run_index(repo: str, token: str, api_url: str, pages: int) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    total = 0
    for page in range(1, pages + 1):
        query = urlencode({"per_page": 100, "page": page})
        payload = github_get(f"{api_url}/repos/{repo}/actions/runs?{query}", token)
        runs = payload.get("workflow_runs", [])
        if not runs:
            break
        total += len(runs)
        for run in runs:
            path = (run.get("path") or "").split("@", 1)[0]
            if not path:
                continue
            counts[path] += 1
            current = latest.get(path)
            stamp = run.get("updated_at") or run.get("created_at") or ""
            current_stamp = (current or {}).get("updated_at") or (current or {}).get("created_at") or ""
            if current is None or stamp > current_stamp:
                latest[path] = run
        if len(runs) < 100:
            break
    return latest, {"sampled_runs": total, "pages_requested": pages, "counts": dict(counts)}


def classify(record: WorkflowRecord, duplicate_size: int) -> tuple[str, str, bool, list[str]]:
    name_lower = record.name.lower()
    path_lower = record.path.lower()
    triggers = set(record.triggers)
    rationale: list[str] = []

    if path_lower.endswith("/ci.yml"):
        return "MANTER", "alta", False, ["orquestrador central de CI"]

    if path_lower.endswith("/actions-dispatcher.yml"):
        rationale.append("mantido somente como disparo manual após remoção dos gatilhos automáticos redundantes")
        return "TRANSFORMAR_EM_REUTILIZAVEL", "alta", True, rationale

    if "workflow_call" in triggers and not (triggers - {"workflow_call", "workflow_dispatch"}):
        return "MANTER", "alta", False, ["já atua como workflow reutilizável"]

    if record.participates_in_deploy or any(keyword in name_lower for keyword in ("deploy", "release", "backup", "restore")):
        rationale.append("participa de entrega, recuperação ou operação de ambiente")
        return "MANTER", "alta", False, rationale

    core_signal = any(keyword in f"{name_lower} {path_lower}" for keyword in CORE_KEYWORDS)
    support_signal = any(keyword in f"{name_lower} {path_lower}" for keyword in SUPPORT_KEYWORDS)
    manual_only = bool(triggers) and triggers <= {"workflow_dispatch"}
    cascading = "workflow_run" in triggers

    if duplicate_size > 1 and support_signal:
        rationale.append(f"grupo funcional com {duplicate_size} workflows semelhantes")
        if cascading:
            rationale.append("acionamento em cascata via workflow_run")
        return "FUNDIR", "media", True, rationale

    if cascading and (support_signal or record.writes_comments_or_evidence):
        rationale.append("workflow de acompanhamento/evidência acionado por outro workflow")
        return "FUNDIR", "media", True, rationale

    if manual_only and support_signal and not core_signal:
        rationale.append("execução exclusivamente manual e função de apoio")
        return "TRANSFORMAR_EM_REUTILIZAVEL", "media", True, rationale

    if not record.last_use_observed_at and support_signal and not record.callers:
        rationale.append("não observado na amostra recente e sem dependente estático encontrado")
        return "REMOVER", "baixa", True, rationale

    if duplicate_size > 1:
        rationale.append(f"possível sobreposição no grupo funcional ({duplicate_size})")
        return "FUNDIR", "baixa", True, rationale

    rationale.append("nenhuma redundância objetiva suficiente para remoção automática")
    return "MANTER", "media" if core_signal else "baixa", not core_signal, rationale


def build_inventory(workflows: dict[str, str], latest_runs: dict[str, dict[str, Any]], run_meta: dict[str, Any]) -> list[WorkflowRecord]:
    name_by_path = {path: parse_name(text, Path(path).stem) for path, text in workflows.items()}
    path_by_name = {name: path for path, name in name_by_path.items()}
    callers: dict[str, set[str]] = defaultdict(set)
    direct_calls: dict[str, set[str]] = defaultdict(set)

    for source_path, text in workflows.items():
        path_calls, name_calls = parse_calls(text)
        for target_path in path_calls:
            direct_calls[source_path].add(target_path)
            if target_path in workflows:
                callers[target_path].add(source_path)
        for target_name in name_calls:
            target_path = path_by_name.get(target_name)
            if target_path:
                direct_calls[source_path].add(target_path)
                callers[target_path].add(source_path)

    preliminary: list[WorkflowRecord] = []
    groups: Counter[str] = Counter()
    for path, text in workflows.items():
        name = name_by_path[path]
        cluster = normalized_cluster(path, name)
        groups[cluster] += 1
        run = latest_runs.get(path)
        lower = text.lower()
        record = WorkflowRecord(
            path=path,
            name=name,
            triggers=parse_triggers(text),
            callers=sorted(callers.get(path, set())),
            calls=sorted(direct_calls.get(path, set())),
            permissions=parse_permissions(text),
            secrets=parse_secrets(text),
            artifacts=parse_artifacts(text),
            writes_comments_or_evidence=any(pattern in lower for pattern in EVIDENCE_PATTERNS),
            participates_in_deploy=any(pattern in lower for pattern in DEPLOY_PATTERNS),
            last_use_observed_at=(run or {}).get("updated_at") or (run or {}).get("created_at"),
            last_use_run_url=(run or {}).get("html_url"),
            recent_run_count_in_sample=int(run_meta.get("counts", {}).get(path, 0)),
            duplication_group=cluster,
            recommendation="",
            confidence="",
            requires_human_validation=True,
            rationale=[],
        )
        preliminary.append(record)

    for record in preliminary:
        rec, confidence, human, rationale = classify(record, groups[record.duplication_group or ""])
        record.recommendation = rec
        record.confidence = confidence
        record.requires_human_validation = human
        record.rationale = rationale
        if groups[record.duplication_group or ""] <= 1:
            record.duplication_group = None
    return preliminary


def write_reports(records: list[WorkflowRecord], output_dir: Path, metadata: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "metadata": metadata,
        "summary": {
            "total_workflows": len(records),
            "recommendations": dict(Counter(record.recommendation for record in records)),
            "with_secrets": sum(bool(record.secrets) for record in records),
            "with_artifacts": sum(bool(record.artifacts) for record in records),
            "with_deploy_signal": sum(record.participates_in_deploy for record in records),
            "not_observed_in_recent_sample": sum(not record.last_use_observed_at for record in records),
        },
        "workflows": [asdict(record) for record in records],
    }
    (output_dir / "workflows.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fields = [field.name for field in WorkflowRecord.__dataclass_fields__.values()]
    with (output_dir / "workflows.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = asdict(record)
            for key, value in list(row.items()):
                if isinstance(value, list):
                    row[key] = " | ".join(str(item) for item in value)
            writer.writerow(row)

    summary = payload["summary"]
    lines = [
        "# Auditoria dos GitHub Actions",
        "",
        f"Gerado em: `{payload['generated_at']}`",
        f"Workflows analisados: **{summary['total_workflows']}**",
        f"Execuções amostradas: **{metadata.get('sampled_runs', 0)}**",
        "",
        "## Recomendações",
        "",
        "| Recomendação | Quantidade |",
        "|---|---:|",
    ]
    for key in ("MANTER", "FUNDIR", "TRANSFORMAR_EM_REUTILIZAVEL", "REMOVER"):
        lines.append(f"| {key} | {summary['recommendations'].get(key, 0)} |")
    lines.extend([
        "",
        "## Critério de segurança",
        "",
        "`REMOVER` com confiança baixa é apenas candidato e exige validação humana; o auditor nunca exclui workflows.",
        "",
        "## Inventário",
        "",
        "| Workflow | Gatilhos | Dependentes | Último uso observado | Recomendação | Confiança |",
        "|---|---|---:|---|---|---|",
    ])
    for record in records:
        lines.append(
            f"| `{record.path}` | {', '.join(record.triggers) or '-'} | {len(record.callers)} | "
            f"{record.last_use_observed_at or 'não observado'} | {record.recommendation} | {record.confidence} |"
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audita e classifica workflows GitHub Actions.")
    parser.add_argument("--workflow-dir", default=str(WORKFLOW_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    parser.add_argument("--runs-sample-pages", type=int, default=10)
    parser.add_argument("--offline", action="store_true", help="Não consulta execuções na API do GitHub.")
    parser.add_argument("--require-api", action="store_true", help="Falha se a coleta de uso via API não for possível.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workflows = read_workflows(Path(args.workflow_dir))
    if not workflows:
        print("Nenhum workflow encontrado.", file=sys.stderr)
        return 2

    latest_runs: dict[str, dict[str, Any]] = {}
    metadata: dict[str, Any] = {"sampled_runs": 0, "pages_requested": args.runs_sample_pages, "counts": {}, "api_status": "offline"}
    if not args.offline:
        token = os.environ.get("GITHUB_TOKEN")
        if not token or not args.repo:
            message = "GITHUB_TOKEN e --repo/GITHUB_REPOSITORY são necessários para coletar último uso."
            if args.require_api:
                print(message, file=sys.stderr)
                return 3
            metadata["api_status"] = "unavailable"
            metadata["api_error"] = message
        else:
            try:
                latest_runs, metadata = fetch_recent_run_index(args.repo, token, args.api_url.rstrip("/"), max(1, args.runs_sample_pages))
                metadata["api_status"] = "ok"
            except RuntimeError as exc:
                if args.require_api:
                    print(str(exc), file=sys.stderr)
                    return 3
                metadata["api_status"] = "error"
                metadata["api_error"] = str(exc)

    records = build_inventory(workflows, latest_runs, metadata)
    write_reports(records, Path(args.output_dir), metadata)
    print(json.dumps({
        "total_workflows": len(records),
        "recommendations": dict(Counter(record.recommendation for record in records)),
        "api_status": metadata.get("api_status"),
        "sampled_runs": metadata.get("sampled_runs", 0),
        "output_dir": args.output_dir,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
