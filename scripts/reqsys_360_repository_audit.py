#!/usr/bin/env python3
"""Inventário estático e não destrutivo das fases 2–6 do ReqSys 360.

Heurísticas produzem inventário/avisos. Somente contratos explícitos de governança
incompletos ou inconsistentes são bloqueantes, para evitar falsos positivos.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

RUNTIME_EXTENSIONS = {".js", ".ts", ".mjs", ".cjs", ".vue"}
TEXT_EXTENSIONS = {".py", ".js", ".ts", ".mjs", ".cjs", ".vue", ".md", ".yml", ".yaml", ".json", ".toml", ".txt", ".ps1", ".sh"}
EVIDENCE_CLASSES = {"real-external", "integration-local", "controlled-ui-mock", "static-contract"}


def is_test_path(path: Path) -> bool:
    text = path.as_posix()
    return "/__tests__/" in text or bool(re.search(r"\.(?:test|spec)\.(?:js|ts|mjs|cjs|vue)$", text))


def walk_runtime_frontend(repo: Path) -> list[Path]:
    root = repo / "frontend" / "src"
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file() and p.suffix in RUNTIME_EXTENSIONS and not is_test_path(p)]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return default


def normalize_url(value: str) -> str:
    value = value.split("?", 1)[0].split("#", 1)[0]
    if value != "/":
        value = value.rstrip("/")
    return value or "/"


def route_regex(route: str) -> re.Pattern[str]:
    escaped = re.escape(normalize_url(route))
    escaped = re.sub(r"\\\{[^{}]+\\\}", r"[^/]+", escaped)
    return re.compile(rf"^{escaped}$")


def path_matches(path: str, routes: Iterable[str]) -> bool:
    normalized = normalize_url(path)
    return any(route_regex(route).match(normalized) for route in routes)


def frontend_api_consumers(repo: Path) -> list[dict]:
    pattern = re.compile(r"(?P<quote>['\"`])(?P<path>/api/[A-Za-z0-9_./:{}-]+)(?P=quote)")
    consumers: list[dict] = []
    for file in walk_runtime_frontend(repo):
        source = read_text(file)
        for match in pattern.finditer(source):
            consumers.append({
                "path": normalize_url(match.group("path")),
                "file": file.relative_to(repo).as_posix(),
                "line": source.count("\n", 0, match.start()) + 1,
            })
    unique = {(item["path"], item["file"], item["line"]): item for item in consumers}
    return sorted(unique.values(), key=lambda item: (item["path"], item["file"], item["line"]))


def backend_routes(repo: Path) -> list[dict]:
    root = repo / "backend" / "app"
    routes: list[dict] = []
    if not root.exists():
        return routes

    prefix_re = re.compile(r"APIRouter\([\s\S]{0,500}?prefix\s*=\s*['\"]([^'\"]+)['\"]")
    decorator_re = re.compile(
        r"@(?P<owner>router|app)\.(?P<method>get|post|put|patch|delete|options|head)"
        r"\(\s*['\"](?P<path>[^'\"]+)['\"]",
        re.IGNORECASE,
    )
    for file in root.rglob("*.py"):
        if "tests" in file.parts or "__pycache__" in file.parts:
            continue
        source = read_text(file)
        prefix = prefix_re.search(source)
        router_prefix = prefix.group(1).rstrip("/") if prefix else ""
        for match in decorator_re.finditer(source):
            path_value = match.group("path")
            if match.group("owner") == "router" and router_prefix and not path_value.startswith(router_prefix + "/"):
                full_path = f"{router_prefix}/{path_value.lstrip('/')}"
            else:
                full_path = path_value
            routes.append({
                "method": match.group("method").upper(),
                "path": normalize_url(full_path),
                "file": file.relative_to(repo).as_posix(),
                "line": source.count("\n", 0, match.start()) + 1,
            })
    unique = {(item["method"], item["path"], item["file"], item["line"]): item for item in routes}
    return sorted(unique.values(), key=lambda item: (item["path"], item["method"], item["file"]))


def router_component_map(repo: Path) -> dict[str, dict]:
    router = repo / "frontend" / "src" / "router" / "index.js"
    source = read_text(router)
    imports = dict(re.findall(r"import\s+([A-Za-z0-9_]+)\s+from\s+['\"]([^'\"]+)['\"]", source))
    result: dict[str, dict] = {}
    route_re = re.compile(r"path\s*:\s*['\"](?P<path>/[^'\"]*)['\"][\s\S]{0,300}?component\s*:\s*(?P<component>[A-Za-z0-9_]+)")
    for match in route_re.finditer(source):
        route = match.group("path")
        if ":pathMatch" in route:
            continue
        component = match.group("component")
        imported = imports.get(component)
        if not imported:
            continue
        view_path = (router.parent / imported).resolve()
        if view_path.suffix == "":
            view_path = view_path.with_suffix(".vue")
        result[route] = {
            "component": component,
            "file": view_path.relative_to(repo).as_posix() if view_path.exists() else None,
        }
    return result


def resolve_relative_import(base: Path, specifier: str) -> Path | None:
    if not specifier.startswith("."):
        return None
    raw = (base.parent / specifier).resolve()
    candidates = [raw]
    if raw.suffix == "":
        candidates.extend(raw.with_suffix(ext) for ext in (".vue", ".js", ".ts", ".mjs", ".cjs"))
        candidates.extend(raw / f"index{ext}" for ext in (".vue", ".js", ".ts"))
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def component_bundle(repo: Path, relative_file: str | None, max_depth: int = 2) -> tuple[str, list[str]]:
    if not relative_file:
        return "", []
    start = repo / relative_file
    visited: set[Path] = set()
    sources: list[str] = []
    files: list[str] = []
    import_re = re.compile(r"import[\s\S]{0,180}?from\s+['\"]([^'\"]+)['\"]")

    def visit(file: Path, depth: int) -> None:
        file = file.resolve()
        if file in visited or not file.is_file() or depth > max_depth:
            return
        try:
            relative = file.relative_to(repo).as_posix()
        except ValueError:
            return
        if is_test_path(file):
            return
        visited.add(file)
        source = read_text(file)
        sources.append(source)
        files.append(relative)
        if depth == max_depth:
            return
        for match in import_re.finditer(source):
            child = resolve_relative_import(file, match.group(1))
            if child is not None:
                visit(child, depth + 1)

    visit(start, 0)
    return "\n".join(sources), files


def ui_state_inventory(repo: Path) -> list[dict]:
    state_patterns = {
        "loading": re.compile(r"\b(carregando|loading|isLoading)\b", re.IGNORECASE),
        "error": re.compile(r"\b(erro|error|falha)\b", re.IGNORECASE),
        "empty": re.compile(r"\b(vazio|empty|sem dados|nenhum|nenhuma)\b", re.IGNORECASE),
        "blocked": re.compile(r"\b(bloqueado|blocked|unauthorized|forbidden|não autorizado|sem permissão)\b", re.IGNORECASE),
        "offline": re.compile(r"\b(offline|modoOffline)\b", re.IGNORECASE),
    }
    async_pattern = re.compile(r"\bawait\b|\bfetch\s*\(|\bapi\.(?:get|post|put|patch|delete)\s*\(|\baxios\b|\bonMounted\s*\(", re.IGNORECASE)
    inventory = []
    for route, info in router_component_map(repo).items():
        source, files = component_bundle(repo, info.get("file"))
        states = {name: bool(pattern.search(source)) for name, pattern in state_patterns.items()}
        dynamic = bool(async_pattern.search(source))
        inventory.append({
            "route": route,
            "component": info["component"],
            "file": info.get("file"),
            "inspected_files": files,
            "kind": "dynamic" if dynamic else "static",
            "states": states,
            "state_count": sum(states.values()),
        })
    return sorted(inventory, key=lambda item: item["route"])


def correlation_inventory(repo: Path) -> dict:
    pattern = re.compile(r"correlation[_-]?id|x-correlation-id", re.IGNORECASE)
    buckets: dict[str, list[str]] = defaultdict(list)
    roots = [repo / "frontend" / "src", repo / "backend" / "app", repo / "runtime", repo / "services"]
    for root in roots:
        if not root.exists():
            continue
        for file in root.rglob("*"):
            if not file.is_file() or file.suffix.lower() not in {".py", ".js", ".ts", ".mjs", ".cjs", ".vue"}:
                continue
            if is_test_path(file):
                continue
            if pattern.search(read_text(file)):
                buckets[file.relative_to(repo).parts[0]].append(file.relative_to(repo).as_posix())
    return {name: sorted(values) for name, values in sorted(buckets.items())}


def observability_inventory(repo: Path, routes: list[dict]) -> list[dict]:
    marker = re.compile(r"health|readiness|liveness|metrics|monitor|analytics|observ", re.IGNORECASE)
    result = []
    for item in routes:
        if not marker.search(item["path"]):
            continue
        source = read_text(repo / item["file"])
        path_value = item["path"].lower()
        if "readiness" in path_value:
            category = "readiness"
        elif "liveness" in path_value:
            category = "liveness"
        elif "health" in path_value:
            category = "health"
        elif "metrics" in path_value:
            category = "metrics"
        elif "analytics" in path_value:
            category = "analytics"
        else:
            category = "monitoring"
        result.append({
            **item,
            "category": category,
            "correlation_aware": bool(re.search(r"correlation[_-]?id|x-correlation-id", source, re.IGNORECASE)),
            "sha_aware": bool(re.search(r"\b(commit_sha|git_sha|head_sha|sha)\b", source, re.IGNORECASE)),
            "environment_aware": bool(re.search(r"\b(environment|ambiente|env)\b", source, re.IGNORECASE)),
        })
    return result


def service_candidates(repo: Path) -> list[dict]:
    services = repo / "frontend" / "src" / "services"
    runtime_files = walk_runtime_frontend(repo)
    contents = {file: read_text(file) for file in runtime_files}
    candidates = []
    if not services.exists():
        return candidates
    for file in services.glob("*.js"):
        stem = file.stem
        hits = []
        needle_variants = [f"services/{stem}", f"./{stem}", f"../services/{stem}"]
        for other, source in contents.items():
            if other == file:
                continue
            if any(needle in source for needle in needle_variants):
                hits.append(other.relative_to(repo).as_posix())
        if not hits:
            candidates.append({"file": file.relative_to(repo).as_posix(), "reason": "sem importação estática detectada"})
    return sorted(candidates, key=lambda item: item["file"])


def architecture_variants(repo: Path, governance: dict) -> list[dict]:
    result = []
    declared = {item["path"]: item for item in governance.get("architectural_variants", [])}
    for name in ["frontend", "frontend-angular", "frontend-vuetify", "backend", "backend-dotnet", "runtime", "services"]:
        if not (repo / name).exists():
            continue
        meta = declared.get(name, {})
        result.append({
            "path": name,
            "classification": meta.get("classification", "unclassified"),
            "responsibility": meta.get("responsibility", ""),
        })
    return result


def load_governance(repo: Path) -> dict:
    return load_json(repo / "governance" / "reqsys-360" / "route-responsibilities.json", {})


def load_journeys(repo: Path) -> dict:
    return load_json(repo / "governance" / "reqsys-360" / "journeys.json", {"journeys": []})


def validate_governance(governance: dict) -> list[dict]:
    findings = []
    routes = governance.get("routes", [])
    seen = set()
    for entry in routes:
        route = entry.get("route")
        if not route or not entry.get("area") or not entry.get("responsibility") or not entry.get("status"):
            findings.append({"severity": "critical", "code": "GOVERNANCE_ROUTE_INCOMPLETE", "message": f"Entrada de responsabilidade incompleta: {entry}"})
            continue
        if route in seen:
            findings.append({"severity": "critical", "code": "GOVERNANCE_ROUTE_DUPLICATE", "message": f"Rota duplicada no contrato de responsabilidade: {route}"})
        seen.add(route)
    for entry in governance.get("navigation_duplicate_decisions", []):
        if not entry.get("route") or not entry.get("classification") or not entry.get("rationale"):
            findings.append({"severity": "critical", "code": "GOVERNANCE_NAV_DECISION_INCOMPLETE", "message": f"Decisão de duplicidade incompleta: {entry}"})
    for entry in governance.get("component_reuse_decisions", []):
        if not entry.get("component") or len(entry.get("paths", [])) < 2 or not entry.get("classification") or not entry.get("rationale"):
            findings.append({"severity": "critical", "code": "GOVERNANCE_COMPONENT_DECISION_INCOMPLETE", "message": f"Decisão de reutilização incompleta: {entry}"})
    return findings


def validate_journeys(repo: Path, journeys_payload: dict) -> list[dict]:
    findings = []
    seen = set()
    for journey in journeys_payload.get("journeys", []):
        journey_id = journey.get("id")
        required = ["id", "name", "entry", "action", "effect", "evidence_class", "evidence_files"]
        missing = [field for field in required if not journey.get(field)]
        if missing:
            findings.append({"severity": "critical", "code": "JOURNEY_CONTRACT_INCOMPLETE", "message": f"Jornada {journey_id or '<sem-id>'} sem campos: {', '.join(missing)}"})
            continue
        if journey_id in seen:
            findings.append({"severity": "critical", "code": "JOURNEY_ID_DUPLICATE", "message": f"Jornada duplicada: {journey_id}"})
        seen.add(journey_id)
        if journey["evidence_class"] not in EVIDENCE_CLASSES:
            findings.append({"severity": "critical", "code": "JOURNEY_EVIDENCE_CLASS_INVALID", "message": f"Classe de evidência inválida em {journey_id}: {journey['evidence_class']}"})
        for evidence_file in journey.get("evidence_files", []):
            if not (repo / evidence_file).is_file():
                findings.append({"severity": "critical", "code": "JOURNEY_EVIDENCE_FILE_MISSING", "message": f"Evidência inexistente em {journey_id}: {evidence_file}"})
        if journey.get("mutable_effect"):
            if not journey.get("positive_control"):
                findings.append({"severity": "critical", "code": "JOURNEY_POSITIVE_CONTROL_MISSING", "message": f"Jornada mutável sem caso positivo declarado: {journey_id}"})
            if not journey.get("independent_read"):
                findings.append({"severity": "critical", "code": "JOURNEY_INDEPENDENT_READ_MISSING", "message": f"Jornada mutável sem leitura independente: {journey_id}"})
            if not journey.get("negative_control") and not journey.get("negative_not_applicable_reason"):
                findings.append({"severity": "critical", "code": "JOURNEY_NEGATIVE_CONTROL_MISSING", "message": f"Jornada mutável sem controle negativo: {journey_id}"})
        if journey.get("idempotency_applicable") and not journey.get("idempotency_verified"):
            findings.append({"severity": "critical", "code": "JOURNEY_IDEMPOTENCY_MISSING", "message": f"Jornada idempotente sem evidência declarada: {journey_id}"})
    return findings


def text_corpus(repo: Path) -> list[Path]:
    roots = [repo / ".github", repo / "backend", repo / "frontend", repo / "runtime", repo / "services", repo / "scripts", repo / "tests", repo / "docs", repo / "governance"]
    result = []
    for root in roots:
        if not root.exists():
            continue
        for file in root.rglob("*"):
            if not file.is_file() or file.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            parts = set(file.parts)
            if {"node_modules", ".git", "artifacts", "dist"} & parts:
                continue
            try:
                if file.stat().st_size > 1_000_000:
                    continue
            except OSError:
                continue
            result.append(file)
    return result


def reference_inventory(repo: Path) -> dict:
    corpus_files = text_corpus(repo)
    corpus = {file: read_text(file) for file in corpus_files}

    def refs_for(file: Path) -> int:
        rel = file.relative_to(repo).as_posix()
        basename = file.name
        stem = file.stem
        total = 0
        for other, source in corpus.items():
            if other == file:
                continue
            if rel in source or basename in source or re.search(rf"(?<![A-Za-z0-9_-]){re.escape(stem)}(?![A-Za-z0-9_-])", source):
                total += 1
        return total

    scripts = []
    scripts_root = repo / "scripts"
    if scripts_root.exists():
        for file in scripts_root.rglob("*"):
            if file.is_file() and file.suffix.lower() in {".py", ".js", ".mjs", ".cjs", ".ps1", ".sh"}:
                scripts.append({"file": file.relative_to(repo).as_posix(), "references": refs_for(file)})

    docs = []
    docs_root = repo / "docs"
    if docs_root.exists():
        for file in list(docs_root.rglob("*.md"))[:500]:
            docs.append({"file": file.relative_to(repo).as_posix(), "references": refs_for(file)})

    return {
        "scripts": sorted(scripts, key=lambda item: item["file"]),
        "docs": sorted(docs, key=lambda item: item["file"]),
        "unreferenced_scripts": sorted([item for item in scripts if item["references"] == 0], key=lambda item: item["file"]),
        "unreferenced_docs": sorted([item for item in docs if item["references"] == 0], key=lambda item: item["file"]),
    }


def generate_report(repo: Path) -> dict:
    governance = load_governance(repo)
    journeys_payload = load_journeys(repo)
    api_consumers = frontend_api_consumers(repo)
    routes = backend_routes(repo)
    backend_paths = [item["path"] for item in routes]
    unresolved_consumers = [item for item in api_consumers if not path_matches(item["path"], backend_paths)]
    backend_without_frontend_literal = [item for item in routes if not any(path_matches(consumer["path"], [item["path"]]) for consumer in api_consumers)]
    ui_states = ui_state_inventory(repo)
    weak_ui_states = [item for item in ui_states if item["kind"] == "dynamic" and item["state_count"] < 2]
    correlations = correlation_inventory(repo)
    service_orphans = service_candidates(repo)
    variants = architecture_variants(repo, governance)
    observability = observability_inventory(repo, routes)
    observability_groups: dict[str, list[str]] = defaultdict(list)
    for item in observability:
        observability_groups[item["category"]].append(item["path"])
    duplicate_observability = {key: sorted(set(values)) for key, values in observability_groups.items() if len(set(values)) > 1}
    observability_without_linkage = [item for item in observability if not item["correlation_aware"] and not item["sha_aware"] and not item["environment_aware"]]
    references = reference_inventory(repo)

    findings = validate_governance(governance) + validate_journeys(repo, journeys_payload)
    for item in unresolved_consumers:
        findings.append({"severity": "info", "code": "API_CONSUMER_UNRESOLVED_STATICALLY", "message": f"Consumidor frontend sem rota backend literal conciliada: {item['path']}", **item})
    for item in weak_ui_states:
        findings.append({"severity": "warning", "code": "UI_STATE_COVERAGE_LOW", "message": f"{item['route']} é dinâmica e expõe menos de dois estados explícitos detectáveis, incluindo componentes locais.", "route": item["route"], "states": item["states"]})
    for item in service_orphans:
        findings.append({"severity": "info", "code": "SERVICE_WITHOUT_STATIC_IMPORT", "message": f"Candidato a serviço sem consumidor estático: {item['file']}", **item})

    summary = {
        "frontend_api_consumers": len(api_consumers),
        "backend_routes": len(routes),
        "unresolved_frontend_consumers": len(unresolved_consumers),
        "backend_routes_without_frontend_literal": len(backend_without_frontend_literal),
        "ui_routes": len(ui_states),
        "ui_dynamic_routes": sum(1 for item in ui_states if item["kind"] == "dynamic"),
        "ui_routes_low_state_coverage": len(weak_ui_states),
        "observability_endpoints": len(observability),
        "observability_duplicate_groups": len(duplicate_observability),
        "observability_without_runtime_linkage": len(observability_without_linkage),
        "correlation_files": sum(len(items) for items in correlations.values()),
        "service_orphan_candidates": len(service_orphans),
        "architectural_variants": len(variants),
        "unclassified_architectural_variants": sum(1 for item in variants if item["classification"] == "unclassified"),
        "journeys": len(journeys_payload.get("journeys", [])),
        "journey_contract_violations": sum(1 for item in findings if item["code"].startswith("JOURNEY_")),
        "unreferenced_scripts": len(references["unreferenced_scripts"]),
        "unreferenced_docs": len(references["unreferenced_docs"]),
        "critical": sum(1 for item in findings if item["severity"] == "critical"),
        "warning": sum(1 for item in findings if item["severity"] == "warning"),
        "info": sum(1 for item in findings if item["severity"] == "info"),
    }
    return {
        "schema_version": 2,
        "summary": summary,
        "findings": findings,
        "route_responsibilities": governance.get("routes", []),
        "overlap_decisions": governance.get("overlap_decisions", []),
        "journeys": journeys_payload.get("journeys", []),
        "api": {
            "frontend_consumers": api_consumers,
            "backend_routes": routes,
            "unresolved_frontend_consumers": unresolved_consumers,
            "backend_without_frontend_literal": backend_without_frontend_literal[:500],
        },
        "ui_states": ui_states,
        "observability": {
            "endpoints": observability,
            "duplicate_groups": duplicate_observability,
            "without_runtime_linkage": observability_without_linkage,
        },
        "correlation": correlations,
        "architecture_variants": variants,
        "service_orphan_candidates": service_orphans,
        "references": references,
    }


def markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# ReqSys 360 — Inventário de Consolidação, Confiabilidade e Operação",
        "",
        f"- Consumidores API no frontend: **{s['frontend_api_consumers']}**",
        f"- Rotas backend detectadas: **{s['backend_routes']}**",
        f"- Consumidores não conciliados estaticamente: **{s['unresolved_frontend_consumers']}** (informativo)",
        f"- Endpoints backend sem consumidor literal no frontend: **{s['backend_routes_without_frontend_literal']}** (inventário, não órfão automático)",
        f"- Rotas de UI: **{s['ui_routes']}**; dinâmicas: **{s['ui_dynamic_routes']}**; baixa cobertura explícita: **{s['ui_routes_low_state_coverage']}**",
        f"- Endpoints de observabilidade: **{s['observability_endpoints']}** em **{s['observability_duplicate_groups']}** grupos sobrepostos",
        f"- Observabilidade sem vínculo estático a correlação/SHA/ambiente: **{s['observability_without_runtime_linkage']}**",
        f"- Arquivos com correlação: **{s['correlation_files']}**",
        f"- Candidatos a serviço sem importação estática: **{s['service_orphan_candidates']}**",
        f"- Variantes arquiteturais: **{s['architectural_variants']}**; não classificadas: **{s['unclassified_architectural_variants']}**",
        f"- Jornadas governadas: **{s['journeys']}**; violações de contrato: **{s['journey_contract_violations']}**",
        f"- Scripts sem referência detectada: **{s['unreferenced_scripts']}**; documentos sem referência detectada: **{s['unreferenced_docs']}**",
        f"- Críticos: **{s['critical']}** · Avisos: **{s['warning']}** · Informativos: **{s['info']}**",
        "",
        "## Responsabilidades canônicas",
        "",
        "| Rota | Área | Estado | Responsabilidade |",
        "|---|---|---|---|",
    ]
    for item in report.get("route_responsibilities", []):
        lines.append(f"| `{item['route']}` | {item['area']} | {item['status']} | {item['responsibility'].replace('|', '/')} |")

    lines.extend(["", "## Decisões de sobreposição", ""])
    for item in report.get("overlap_decisions", []):
        lines.append(f"- **{item['subject']}**: {item['decision']}")

    lines.extend(["", "## Jornadas e classe de evidência", "", "| Jornada | Classe | Efeito mutável | Leitura independente | Negativo | Idempotência |", "|---|---|---|---|---|---|"])
    for item in report.get("journeys", []):
        lines.append(
            f"| {item.get('name', item.get('id'))} | {item.get('evidence_class', '')} | "
            f"{'sim' if item.get('mutable_effect') else 'não'} | "
            f"{'sim' if item.get('independent_read') else 'não'} | "
            f"{'sim' if item.get('negative_control') else 'n/a'} | "
            f"{'sim' if item.get('idempotency_verified') else ('pendente' if item.get('idempotency_applicable') else 'n/a')} |"
        )

    lines.extend(["", "## Achados", "", "| Severidade | Código | Mensagem |", "|---|---|---|"])
    for item in report.get("findings", []):
        icon = "🔴" if item["severity"] == "critical" else "🟡" if item["severity"] == "warning" else "ℹ️"
        lines.append(f"| {icon} {item['severity']} | `{item['code']}` | {item['message'].replace('|', '/')} |")
    if not report.get("findings"):
        lines.append("| 🟢 | `OK` | Nenhuma inconsistência detectada. |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    report = generate_report(repo)
    output = repo / "artifacts" / "reqsys-360"
    output.mkdir(parents=True, exist_ok=True)
    (output / "repository-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "repository-audit.md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
