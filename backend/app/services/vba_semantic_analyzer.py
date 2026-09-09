from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.vba_legacy_analyzer import analyze_vba_source

SEMANTIC_SCHEMA_VERSION = '1.0.0'

_ASSIGNMENT_RE = re.compile(r'^\s*(?:Set\s+)?(.+?)\s*=\s*(.+)$', re.IGNORECASE)
_IDENTIFIER_RE = re.compile(r'\b[A-Za-z_]\w*\b')
_RANGE_RE = re.compile(r'(?:(?:Worksheets|Sheets)\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\.)?Range\s*\(\s*["\']([^"\']+)["\']\s*\)', re.IGNORECASE)
_CELLS_RE = re.compile(r'(?:(?:Worksheets|Sheets)\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\.)?Cells\s*\(\s*([^\)]+)\)', re.IGNORECASE)
_SQL_LITERAL_RE = re.compile(r'["\']\s*(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|EXEC(?:UTE)?)\b', re.IGNORECASE)
_EXECUTE_RE = re.compile(r'\b(?:Execute|CommandText\s*=)\s*(.+)$', re.IGNORECASE)
_FILE_OPEN_RE = re.compile(r'^\s*Open\s+(.+?)\s+For\s+(Output|Append|Binary|Random)\b', re.IGNORECASE)
_PRINT_RE = re.compile(r'^\s*Print\s+#\d+\s*,?\s*(.+)$', re.IGNORECASE)
_SEND_RE = re.compile(r'\.Send\b', re.IGNORECASE)
_SECRET_RE = re.compile(r'(?i)(password|pwd)\s*=\s*[^;"\']+')
_KEYWORDS = {
    'as', 'and', 'or', 'not', 'true', 'false', 'nothing', 'set', 'new', 'if', 'then',
    'else', 'elseif', 'end', 'sub', 'function', 'property', 'call', 'byval', 'byref',
    'dim', 'public', 'private', 'friend', 'const', 'select', 'case', 'for', 'next', 'do',
    'loop', 'while', 'wend', 'with', 'me', 'thisworkbook', 'activeworkbook', 'activesheet',
}


@dataclass(frozen=True)
class ProcedureContext:
    name: str
    start_line: int
    end_line: int
    parameters: tuple[str, ...]


def _clean(value: str, limit: int = 180) -> str:
    value = _SECRET_RE.sub(r'\1=<redacted>', value.strip())
    return value if len(value) <= limit else f'{value[: limit - 3]}...'


def _parameter_name(raw: str) -> str | None:
    text = re.sub(r'(?i)\b(ByVal|ByRef|Optional|ParamArray)\b', '', raw).strip()
    match = re.match(r'([A-Za-z_]\w*)', text)
    return match.group(1) if match else None


def _procedures(base: dict[str, object]) -> list[ProcedureContext]:
    result: list[ProcedureContext] = []
    for proc in base.get('procedures') or []:
        params = tuple(
            name
            for raw in proc.get('parameters') or []
            if (name := _parameter_name(str(raw)))
        )
        result.append(
            ProcedureContext(
                name=str(proc['name']),
                start_line=int(proc['start_line']),
                end_line=int(proc['end_line']),
                parameters=params,
            )
        )
    return result


def _procedure_for_line(procedures: list[ProcedureContext], line_no: int) -> ProcedureContext | None:
    return next((proc for proc in procedures if proc.start_line <= line_no <= proc.end_line), None)


def _excel_refs(expression: str) -> list[str]:
    refs: list[str] = []
    for sheet, address in _RANGE_RE.findall(expression):
        refs.append(f'{sheet or "<active_sheet>"}!{address}')
    for sheet, coordinates in _CELLS_RE.findall(expression):
        refs.append(f'{sheet or "<active_sheet>"}!Cells({coordinates.strip()})')
    return refs


def _identifiers(expression: str) -> list[str]:
    result: list[str] = []
    for token in _IDENTIFIER_RE.findall(expression):
        lower = token.lower()
        if lower in _KEYWORDS or token.isdigit():
            continue
        if token not in result:
            result.append(token)
    return result


def _node_id(kind: str, name: str) -> str:
    normalized = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'value'
    return f'{kind}:{normalized}'


def _classify_target(target: str, procedure: ProcedureContext | None) -> tuple[str, str]:
    refs = _excel_refs(target)
    if refs:
        return 'excel_output', refs[0]
    target_name = target.strip()
    if procedure and target_name.lower() == procedure.name.lower():
        return 'return_value', procedure.name
    return 'variable', target_name


def _extract_semantic_flow(source: str, base: dict[str, object]) -> dict[str, object]:
    lines = source.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    procedures = _procedures(base)
    nodes: dict[str, dict[str, object]] = {}
    edges: list[dict[str, object]] = []
    sinks: list[dict[str, object]] = []
    lineage: dict[str, set[str]] = {}

    def add_node(kind: str, name: str, line_no: int | None, procedure: str | None) -> str:
        node_id = _node_id(kind, name)
        nodes.setdefault(
            node_id,
            {'id': node_id, 'type': kind, 'name': name, 'first_line': line_no, 'procedure': procedure},
        )
        return node_id

    def add_edge(source_id: str, target_id: str, relation: str, line_no: int, evidence: str) -> None:
        edges.append(
            {
                'from': source_id,
                'to': target_id,
                'relation': relation,
                'line': line_no,
                'evidence': _clean(evidence),
            }
        )

    for proc in procedures:
        for param in proc.parameters:
            add_node('parameter', f'{proc.name}.{param}', proc.start_line, proc.name)
            lineage.setdefault(param.lower(), set()).add(_node_id('parameter', f'{proc.name}.{param}'))

    for line_no, raw_line in enumerate(lines, 1):
        code = raw_line.split("'", 1)[0].strip()
        if not code:
            continue
        procedure = _procedure_for_line(procedures, line_no)
        proc_name = procedure.name if procedure else None

        assignment = _ASSIGNMENT_RE.match(code)
        if assignment and not re.match(r'(?i)^(If|ElseIf|Do\s+While|Loop\s+While)\b', code):
            target = assignment.group(1).strip()
            expression = assignment.group(2).strip()
            target_kind, target_name = _classify_target(target, procedure)
            target_id = add_node(target_kind, target_name, line_no, proc_name)

            source_ids: set[str] = set()
            for ref in _excel_refs(expression):
                source_ids.add(add_node('excel_input', ref, line_no, proc_name))
            if _SQL_LITERAL_RE.search(expression):
                source_ids.add(add_node('sql_literal', _clean(expression, 120), line_no, proc_name))
            for identifier in _identifiers(expression):
                inherited = lineage.get(identifier.lower())
                if inherited:
                    source_ids.update(inherited)
                else:
                    source_ids.add(add_node('variable', identifier, line_no, proc_name))

            if not source_ids:
                source_ids.add(add_node('literal_or_expression', _clean(expression, 120), line_no, proc_name))
            for source_id in sorted(source_ids):
                add_edge(source_id, target_id, 'assigns_or_transforms', line_no, code)

            if target_kind == 'variable':
                lineage[target_name.lower()] = set(source_ids)
            else:
                sinks.append({'type': target_kind, 'name': target_name, 'line': line_no, 'procedure': proc_name})

        execute = _EXECUTE_RE.search(code)
        if execute:
            expression = execute.group(1).strip()
            sink_id = add_node('database_sink', 'database_command', line_no, proc_name)
            source_ids = set()
            for identifier in _identifiers(expression):
                source_ids.update(lineage.get(identifier.lower(), {_node_id('variable', identifier)}))
                add_node('variable', identifier, line_no, proc_name)
            if _SQL_LITERAL_RE.search(expression):
                source_ids.add(add_node('sql_literal', _clean(expression, 120), line_no, proc_name))
            for source_id in sorted(source_ids):
                add_edge(source_id, sink_id, 'executes_sql', line_no, code)
            sinks.append({'type': 'database_sink', 'name': 'database_command', 'line': line_no, 'procedure': proc_name})

        file_open = _FILE_OPEN_RE.match(code)
        if file_open:
            sink_name = _clean(file_open.group(1), 120)
            add_node('file_sink', sink_name, line_no, proc_name)
            sinks.append({'type': 'file_sink', 'name': sink_name, 'line': line_no, 'procedure': proc_name})

        printed = _PRINT_RE.match(code)
        if printed:
            sink_id = add_node('file_sink', 'open_file_handle', line_no, proc_name)
            for identifier in _identifiers(printed.group(1)):
                source_ids = lineage.get(identifier.lower(), {_node_id('variable', identifier)})
                add_node('variable', identifier, line_no, proc_name)
                for source_id in sorted(source_ids):
                    add_edge(source_id, sink_id, 'writes_file', line_no, code)

        if _SEND_RE.search(code):
            add_node('message_sink', 'message_send', line_no, proc_name)
            sinks.append({'type': 'message_sink', 'name': 'message_send', 'line': line_no, 'procedure': proc_name})

    return {
        'schema_version': SEMANTIC_SCHEMA_VERSION,
        'nodes': sorted(nodes.values(), key=lambda item: (str(item['type']), str(item['name']).lower())),
        'edges': edges,
        'sinks': sinks,
        'summary': {
            'nodes': len(nodes),
            'edges': len(edges),
            'sinks': len(sinks),
            'procedures_with_flow': len({item['procedure'] for item in edges if item['procedure'] is not None}) if edges and 'procedure' in edges[0] else len({edge.get('procedure') for edge in []}),
        },
    }


def _attach_procedure_to_edges(flow: dict[str, object], procedures: list[ProcedureContext]) -> None:
    for edge in flow['edges']:
        procedure = _procedure_for_line(procedures, int(edge['line']))
        edge['procedure'] = procedure.name if procedure else None
    flow['summary']['procedures_with_flow'] = len({edge['procedure'] for edge in flow['edges'] if edge['procedure']})


def _test_candidates(base: dict[str, object], flow: dict[str, object]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for index, rule in enumerate(base.get('business_rules') or [], 1):
        candidates.append(
            {
                'id': f'VBA-TEST-{index:03d}',
                'type': 'business_rule',
                'procedure': rule.get('procedure'),
                'source_line': rule.get('line'),
                'given': f'Entradas que exercitem a condição: {rule.get("expression")}',
                'when': f'Executar logicamente {rule.get("procedure") or base["module"]["name"]} sem automação de interface.',
                'then': f'Validar o efeito esperado: {rule.get("action") or "ramo de decisão correspondente"}.',
                'requires_human_validation': True,
            }
        )
    offset = len(candidates)
    for index, sink in enumerate(flow.get('sinks') or [], 1):
        candidates.append(
            {
                'id': f'VBA-TEST-{offset + index:03d}',
                'type': 'data_flow_sink',
                'procedure': sink.get('procedure'),
                'source_line': sink.get('line'),
                'given': 'Entradas controladas e dependências substituídas por dublês de teste.',
                'when': f'O fluxo alcançar o destino {sink.get("type")}:{sink.get("name")}.',
                'then': 'Validar valor, destino e ausência de efeito colateral fora do contrato esperado.',
                'requires_human_validation': True,
            }
        )
    return candidates


def analyze_vba_semantics(source: str, *, file_name: str = 'module.bas') -> dict[str, object]:
    base = analyze_vba_source(source, file_name=file_name)
    procedures = _procedures(base)
    flow = _extract_semantic_flow(source, base)
    _attach_procedure_to_edges(flow, procedures)
    tests = _test_candidates(base, flow)

    result = dict(base)
    result['schema_version'] = '1.1.0'
    result['semantic_analysis'] = {
        'status': 'CANDIDATE_REQUIRES_HUMAN_VALIDATION',
        'execution_performed': False,
        'source_persisted': False,
        'data_flow': flow,
        'test_candidates': tests,
    }
    result['summary'] = {
        **base['summary'],
        'data_flow_nodes': flow['summary']['nodes'],
        'data_flow_edges': flow['summary']['edges'],
        'data_flow_sinks': flow['summary']['sinks'],
        'test_candidates': len(tests),
    }
    return result
