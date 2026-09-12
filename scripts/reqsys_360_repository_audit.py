#!/usr/bin/env python3
"""Inventário estático e não destrutivo das fases 2–6 do ReqSys 360.

Heurísticas geram inventário/avisos; somente violações determinísticas do contrato
`governance/reqsys-360/route-responsibilities.json` são críticas.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

RUNTIME_EXTENSIONS = {".js", ".ts", ".mjs", ".cjs", ".vue"}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


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
    except UnicodeDecodeError:
        return ""


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
            line = source.count("\n", 0, match.start()) + 1
            consumers.append({
                "path": normalize_url(match.group("path")),
                "file": file.relative_to(repo).as_posix(),
                "line": line,
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
    route_re = re.compile(
        r"path\s*:\s*['\"](?P<path>/[^'\"]*)['\"][\s\S]{0,300}?component\s*:\s*(?P<component>[A-Za-z0-9_]+)"
    )
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


def ui_state_inventory(repo: Path) -> list[dict]:
    state_patterns = {
        "loading": re.compile(r"\b(carregando|loading|isLoading)\b", re.IGNORECASE),
        "error": re.compile(r"\b(erro|error|falha)\b", re.IGNORECASE),
        "empty": re.compile(r"\b(vazio|empty|sem dados|nenhum|nenhuma)\b", re.IGNORECASE),
        "unauthorized": re.compile(r"\b(unauthorized|forbidden|não autorizado|sem permissão|permissão)\b", re.IGNORECASE),
    }
    inventory = []
    for route, info in router_component_map(repo).items():
        file_value = info.get("file")
        source = read_text(repo / file_value) if file_value else ""
        states = {name: bool(pattern.search(source)) for name, pattern in state_patterns.items()}
        inventory.append({
            "route": route,
            "component": info["component"],
            "file": file_value,
            "states": states,
            "state_count": sum(states.values()),
        })
    return sorted(inventory, key=lambda item: item["route"])


def correlation_inventory(repo: Path) -> dict:
    patterns = re.compile(r"correlation[_-]?id|x-correlation-id", re.IGNORECASE)
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
            if patterns.search(read_text(file)):
                top = file.relative_to(repo).parts[0]
                buckets[top].append(file.relative_to(repo).as_posix())
    return {name: sorted(values) for name, values in sorted(buckets.items())}


def observability_inventory(routes: list[dict]) -> list[dict]:
    marker = re.compile(r"health|readiness|liveness|metrics|monitor|analytics|observ", re.IGNORECASE)
    return [item for item in routes if marker.search(item["path"])]


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
    path = repo / "governance" / "reqsys-360" / "route-responsibilities.json"
    if not path.exists():
        return {}
    return json.loads(read_text(path))


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
    return findings


def generate_report(repo: Path) -> dict:
    governance = load_governance(repo)
    api_consumers = frontend_api_consumers(repo)
    routes = backend_routes(repo)
    backend_paths = [item["path"] for item in routes]
    unresolved_consumers = [item for item in api_consumers if not path_matches(item["path"], backend_paths)]
    backend_without_frontend_literal = [item for item in routes if not any(path_matches(consumer["path"], [item["path"]]) for consumer in api_consumers)]
    ui_states = ui_state_inventory(repo)
    weak_ui_states = [item for item in ui_states if item["state_count"] < 2]
    correlations = correlation_inventory(repo)
    service_orphans = service_candidates(repo)
    findings = validate_governance(governance)

    for item in unresolved_consumers:
        findings.append({
            "severity": "info",
            "code": "API_CONSUMER_UNRESOLVED_STATICALLY",
            "message": f"Consumidor frontend sem rota backend literal conciliada: {item['path']}",
            **item,
        })
    for item in weak_ui_states:
        findings.append({
            "severity": "warning",
            "code": "UI_STATE_COVERAGE_LOW",
            "message": f"{item['route']} expõe menos de dois estados explícitos de UI detectáveis.",
            "route": item["route"],
            "states": item["states"],
        })
    for item in service_orphans:
        findings.append({
            "severity": "info",
            "code": "SERVICE_WITHOUT_STATIC_IMPORT",
            "message": f"Candidato a serviço sem consumidor estático: {item['file']}",
            **item,
        })

    summary = {
        "frontend_api_consumers": len(api_consumers),
        "backend_routes": len(routes),
        "unresolved_frontend_consumers": len(unresolved_consumers),
        "backend_routes_without_frontend_literal": len(backend_without_frontend_literal),
        "ui_routes": len(ui_states),
        "ui_routes_low_state_coverage": len(weak_ui_states),
        "observability_endpoints": len(observability_inventory(routes)),
        "correlation_files": sum(len(items) for items in correlations.values()),
        "service_orphan_candidates": len(service_orphans),
        "architectural_variants": len(architecture_variants(repo, governance)),
        "critical": sum(1 for item in findings if item["severity"] == "critical"),
        "warning": sum(1 for item in findings if item["severity"] == "warning"),
        "info": sum(1 for item in findings if item["severity"] == "info"),
    }
    return {
        "schema_version": 1,
        "summary": summary,
        "findings": findings,
        "route_responsibilities": governance.get("routes", []),
        "overlap_decisions": governance.get("overlap_decisions", []),
        "api": {
            "frontend_consumers": api_consumers,
            "backend_routes": routes,
            "unresolved_frontend_consumers": unresolved_consumers,
            "backend_without_frontend_literal": backend_without_frontend_literal[:300],
        },
        "ui_states": ui_states,
        "observability": observability_inventory(routes),
        "correlation": correlations,
        "architecture_variants": architecture_variants(repo, governance),
        "service_orphan_candidates": service_orphans,
    }


def markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# ReqSys 360 — Inventário de Consolidação, Confiabilidade e Operação",
        "",
        f"- Consumidores API no frontend: **{s['frontend_api_consumers']}**",
        f"- Rotas backend detectadas: **{s['backend_routes']}**",
        f"- Consumidores não conciliados estaticamente: **{s['unresolved_frontend_consumers']}** (informativo)",
        f"- Rotas de UI: **{s['ui_routes']}**; baixa cobertura explícita de estados: **{s['ui_routes_low_state_coverage']}**",
        f"- Endpoints de observabilidade: **{s['observability_endpoints']}**",
        f"- Arquivos com correlação: **{s['correlation_files']}**",
        f"- Candidatos a serviço sem importação estática: **{s['service_orphan_candidates']}**",
        f"- Variantes arquiteturais: **{s['architectural_variants']}**",
        f"- Críticos: **{s['critical']}** · Avisos: **{s['warning']}** · Informativos: **{s['info']}**",
        "",
        "## Responsabilidades canônicas",
        "",
        "| Rota | Área | Estado | Responsabilidade |",
        "|---|---|---|---|",
    ]
    for item in report.get("route_responsibilities", []):
        lines.append(f"| `{item['route']}` | {item['area']} | {item['status']} | {item['responsibility']} |")
    lines += ["", "## Decisões de sobreposição", ""]
    for item in report.get("overlap_decisions", []):
        lines.append(f"- **{item['subject']}**: {item['decision']}")
    lines += ["", "## Achados", "", "| Severidade | Código | Mensagem |", "|---|---|---|"]
    for item in report["findings"]:
        icon = {"critical": "🔴", "warning": "🟡", "info": "ℹ️"}[item["severity"]]
        message = str(item["message"]).replace("|", "\\|")
        lines.append(f"| {icon} {item['severity']} | `{item['code']}` | {message} |")
    if not report["findings"]:
        lines.append("| 🟢 | `OK` | Nenhum achado. |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output", default="artifacts/reqsys-360")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    report = generate_report(repo)
    output = repo / args.output
    output.mkdir(parents=True, exist_ok=True)
    (output / "repository-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "repository-audit.md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
