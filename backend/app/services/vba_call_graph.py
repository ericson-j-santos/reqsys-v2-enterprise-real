from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from app.services.vba_semantic_analyzer import analyze_vba_semantics

CALL_GRAPH_SCHEMA_VERSION = "1.0.0"

_CALL_RE = re.compile(
    r"^\s*Call\s+([A-Za-z_]\w*)\s*(?:\((.*)\)|(.*))?$",
    re.IGNORECASE,
)
_RUN_LITERAL_RE = re.compile(
    r"\b(?:Application\.)?Run\s+[\"']([A-Za-z_]\w*)[\"']\s*(?:,\s*(.*))?$",
    re.IGNORECASE,
)
_RUN_DYNAMIC_RE = re.compile(
    r"\b(?:Application\.)?Run\s+([^,\"']+)(?:,\s*(.*))?$",
    re.IGNORECASE,
)
_STRING_LITERAL_RE = re.compile(r'"(?:[^"]|"")*"|\'(?:[^\']|\'\')*\'')
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_]\w*\b")
_DECLARATION_RE = re.compile(
    r"^\s*(?:(?:Public|Private|Friend|Static)\s+)?"
    r"(?:Sub|Function|Property\s+(?:Get|Let|Set))\b",
    re.IGNORECASE,
)
_END_RE = re.compile(r"^\s*End\s+(?:Sub|Function|Property)\b", re.IGNORECASE)


def _sanitize_expression(value: str | None, limit: int = 160) -> str | None:
    if value is None:
        return None
    cleaned = _STRING_LITERAL_RE.sub("<literal>", value.strip())
    cleaned = re.sub(r"(?i)(password|pwd)\s*=\s*[^;,\s]+", r"\1=<redacted>", cleaned)
    return cleaned if len(cleaned) <= limit else f"{cleaned[: limit - 3]}..."


def _split_arguments(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return []
    arguments: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    index = 0

    while index < len(raw):
        char = raw[index]
        if quote:
            current.append(char)
            if char == quote:
                if index + 1 < len(raw) and raw[index + 1] == quote:
                    current.append(raw[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in {'"', "'"}:
            quote = char
            current.append(char)
        elif char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth = max(depth - 1, 0)
            current.append(char)
        elif char == "," and depth == 0:
            arguments.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1

    if current or raw.endswith(","):
        arguments.append("".join(current).strip())
    return arguments


def _parameter_name(raw: object) -> str | None:
    text = re.sub(
        r"(?i)\b(ByVal|ByRef|Optional|ParamArray)\b",
        "",
        str(raw or ""),
    ).strip()
    match = re.match(r"([A-Za-z_]\w*)", text)
    return match.group(1) if match else None


def _source_references(expression: str) -> list[str]:
    without_literals = _STRING_LITERAL_RE.sub(" ", expression)
    ignored = {
        "and",
        "as",
        "byref",
        "byval",
        "false",
        "new",
        "nothing",
        "not",
        "or",
        "true",
    }
    result: list[str] = []
    for token in _IDENTIFIER_RE.findall(without_literals):
        if token.lower() in ignored:
            continue
        if token not in result:
            result.append(token)
    return result


def _procedure_ranges(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    module = str((analysis.get("module") or {}).get("name") or "<module>")
    for procedure in analysis.get("procedures") or []:
        result.append(
            {
                "module": module,
                "name": str(procedure["name"]),
                "start_line": int(procedure["start_line"]),
                "end_line": int(procedure["end_line"]),
                "parameters": [
                    name
                    for raw in procedure.get("parameters") or []
                    if (name := _parameter_name(raw))
                ],
            }
        )
    return result


def _procedure_for_line(
    procedures: list[dict[str, Any]],
    line_no: int,
) -> dict[str, Any] | None:
    return next(
        (
            procedure
            for procedure in procedures
            if procedure["start_line"] <= line_no <= procedure["end_line"]
        ),
        None,
    )


def _node_id(module: str, procedure: str) -> str:
    return f"{module}.{procedure}"


def _known_call_pattern(names: list[str]) -> re.Pattern[str] | None:
    if not names:
        return None
    alternatives = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
    return re.compile(rf"\b({alternatives})\s*\((.*?)\)", re.IGNORECASE)


def _binding_payload(
    arguments: list[str],
    parameters: list[str],
) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for index, argument in enumerate(arguments):
        bindings.append(
            {
                "position": index + 1,
                "parameter": parameters[index] if index < len(parameters) else None,
                "argument": _sanitize_expression(argument),
                "source_references": _source_references(argument),
            }
        )
    return bindings


def _source_call_sites(
    source: str,
    analysis: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    procedures = _procedure_ranges(analysis)
    known_by_lower = {item["name"].lower(): item for item in procedures}
    known_pattern = _known_call_pattern([item["name"] for item in procedures])
    edges: list[dict[str, Any]] = []
    dynamic_calls: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for line_no, raw_line in enumerate(lines, 1):
        code = raw_line.split("'", 1)[0].strip()
        if not code or _DECLARATION_RE.match(code) or _END_RE.match(code):
            continue
        caller = _procedure_for_line(procedures, line_no)
        if caller is None:
            continue

        literal_run = _RUN_LITERAL_RE.search(code)
        if literal_run:
            callee_name = literal_run.group(1)
            arguments = _split_arguments(literal_run.group(2))
            callee = known_by_lower.get(callee_name.lower())
            if callee:
                key = (caller["name"], callee["name"], line_no, "application_run_literal")
                if key not in seen:
                    seen.add(key)
                    edges.append(
                        {
                            "from": _node_id(caller["module"], caller["name"]),
                            "to": _node_id(callee["module"], callee["name"]),
                            "line": line_no,
                            "call_type": "application_run_literal",
                            "confidence": 0.98,
                            "parameter_bindings": _binding_payload(
                                arguments,
                                callee["parameters"],
                            ),
                        }
                    )
            else:
                dynamic_calls.append(
                    {
                        "caller": _node_id(caller["module"], caller["name"]),
                        "line": line_no,
                        "status": "UNRESOLVED_LITERAL_TARGET",
                        "target": callee_name,
                        "evidence": _sanitize_expression(code),
                        "requires_human_review": True,
                    }
                )
            continue

        dynamic_run = _RUN_DYNAMIC_RE.search(code)
        if dynamic_run:
            dynamic_calls.append(
                {
                    "caller": _node_id(caller["module"], caller["name"]),
                    "line": line_no,
                    "status": "DYNAMIC_TARGET",
                    "target": _sanitize_expression(dynamic_run.group(1)),
                    "evidence": _sanitize_expression(code),
                    "requires_human_review": True,
                }
            )
            continue

        explicit_call = _CALL_RE.match(code)
        if explicit_call:
            callee_name = explicit_call.group(1)
            arguments = _split_arguments(explicit_call.group(2) or explicit_call.group(3))
            callee = known_by_lower.get(callee_name.lower())
            if callee:
                key = (caller["name"], callee["name"], line_no, "call_statement")
                if key not in seen:
                    seen.add(key)
                    edges.append(
                        {
                            "from": _node_id(caller["module"], caller["name"]),
                            "to": _node_id(callee["module"], callee["name"]),
                            "line": line_no,
                            "call_type": "call_statement",
                            "confidence": 0.99,
                            "parameter_bindings": _binding_payload(
                                arguments,
                                callee["parameters"],
                            ),
                        }
                    )
            continue

        if known_pattern:
            for match in known_pattern.finditer(code):
                callee = known_by_lower.get(match.group(1).lower())
                if callee is None:
                    continue
                key = (caller["name"], callee["name"], line_no, "function_expression")
                if key in seen:
                    continue
                seen.add(key)
                edges.append(
                    {
                        "from": _node_id(caller["module"], caller["name"]),
                        "to": _node_id(callee["module"], callee["name"]),
                        "line": line_no,
                        "call_type": "function_expression",
                        "confidence": 0.92,
                        "parameter_bindings": _binding_payload(
                            _split_arguments(match.group(2)),
                            callee["parameters"],
                        ),
                    }
                )

    return edges, dynamic_calls


def _cycles(nodes: list[str], edges: list[dict[str, Any]]) -> list[list[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[str(edge["from"])].add(str(edge["to"]))

    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, path: list[str], active: set[str]) -> None:
        if node in active:
            start = path.index(node)
            cycle = path[start:] + [node]
            body = cycle[:-1]
            if body:
                rotations = [
                    tuple(body[index:] + body[:index])
                    for index in range(len(body))
                ]
                cycles.add(min(rotations))
            return
        active.add(node)
        path.append(node)
        for target in sorted(adjacency.get(node, ())):
            visit(target, path, active)
        path.pop()
        active.remove(node)

    for node in sorted(nodes):
        visit(node, [], set())

    return [list(cycle) + [cycle[0]] for cycle in sorted(cycles)]


def _project_graph(analysis: dict[str, Any]) -> dict[str, Any]:
    modules = analysis.get("modules") or []
    nodes: list[dict[str, Any]] = []
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for module in modules:
        module_name = str(module.get("name") or "<module>")
        for procedure in module.get("procedures") or []:
            node = {
                "id": _node_id(module_name, str(procedure["name"])),
                "module": module_name,
                "procedure": str(procedure["name"]),
            }
            nodes.append(node)
            by_name[node["procedure"].lower()].append(node)

    edges: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for module in modules:
        module_name = str(module.get("name") or "<module>")
        for procedure in module.get("procedures") or []:
            caller = _node_id(module_name, str(procedure["name"]))
            for called in procedure.get("calls") or []:
                candidates = by_name.get(str(called).lower(), [])
                if len(candidates) == 1:
                    edges.append(
                        {
                            "from": caller,
                            "to": candidates[0]["id"],
                            "line": None,
                            "call_type": "project_resolved",
                            "confidence": 0.86,
                            "parameter_bindings": [],
                        }
                    )
                elif len(candidates) > 1:
                    unresolved.append(
                        {
                            "caller": caller,
                            "target": str(called),
                            "status": "AMBIGUOUS_TARGET",
                            "candidate_nodes": [
                                candidate["id"] for candidate in candidates
                            ],
                            "requires_human_review": True,
                        }
                    )
                else:
                    unresolved.append(
                        {
                            "caller": caller,
                            "target": str(called),
                            "status": "EXTERNAL_OR_UNRESOLVED",
                            "candidate_nodes": [],
                            "requires_human_review": True,
                        }
                    )

    node_ids = [str(node["id"]) for node in nodes]
    cycles = _cycles(node_ids, edges)
    return {
        "schema_version": CALL_GRAPH_SCHEMA_VERSION,
        "scope": "office_project",
        "nodes": nodes,
        "edges": edges,
        "dynamic_or_unresolved_calls": unresolved,
        "cycles": cycles,
        "summary": {
            "procedures": len(nodes),
            "resolved_edges": len(edges),
            "dynamic_or_unresolved_calls": len(unresolved),
            "cycles": len(cycles),
        },
        "execution_performed": False,
        "requires_human_validation": bool(unresolved or cycles),
    }


def analyze_vba_with_call_graph(
    source: str,
    *,
    file_name: str = "module.bas",
) -> dict[str, Any]:
    analysis = analyze_vba_semantics(source, file_name=file_name)
    procedures = _procedure_ranges(analysis)
    nodes = [
        {
            "id": _node_id(item["module"], item["name"]),
            "module": item["module"],
            "procedure": item["name"],
            "parameters": item["parameters"],
        }
        for item in procedures
    ]
    edges, dynamic_calls = _source_call_sites(source, analysis)
    cycles = _cycles([str(node["id"]) for node in nodes], edges)

    result = dict(analysis)
    result["schema_version"] = "1.2.0"
    result["call_graph"] = {
        "schema_version": CALL_GRAPH_SCHEMA_VERSION,
        "scope": "source_module",
        "nodes": nodes,
        "edges": edges,
        "dynamic_or_unresolved_calls": dynamic_calls,
        "cycles": cycles,
        "summary": {
            "procedures": len(nodes),
            "resolved_edges": len(edges),
            "dynamic_or_unresolved_calls": len(dynamic_calls),
            "cycles": len(cycles),
        },
        "execution_performed": False,
        "requires_human_validation": bool(dynamic_calls or cycles),
    }
    result["summary"] = {
        **analysis["summary"],
        "call_graph_edges": len(edges),
        "dynamic_or_unresolved_calls": len(dynamic_calls),
        "call_cycles": len(cycles),
    }
    return result


def attach_project_call_graph(analysis: dict[str, Any]) -> dict[str, Any]:
    result = dict(analysis)
    graph = _project_graph(analysis)
    result["schema_version"] = "1.3.0"
    result["call_graph"] = graph
    result["summary"] = {
        **(analysis.get("summary") or {}),
        "call_graph_edges": graph["summary"]["resolved_edges"],
        "dynamic_or_unresolved_calls": graph["summary"][
            "dynamic_or_unresolved_calls"
        ],
        "call_cycles": graph["summary"]["cycles"],
    }
    return result
