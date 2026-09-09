from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

SCHEMA_VERSION = '1.0.0'
ANALYZER_NAME = 'reqsys-vba-legacy-static'

_PROCEDURE_RE = re.compile(
    r'^\s*(?:(Public|Private|Friend)\s+)?(?:(Static)\s+)?'
    r'(Sub|Function|Property\s+(?:Get|Let|Set))\s+([A-Za-z_]\w*)\s*'
    r'(?:\((.*?)\))?',
    re.IGNORECASE,
)
_END_PROCEDURE_RE = re.compile(r'^\s*End\s+(Sub|Function|Property)\b', re.IGNORECASE)
_MODULE_RE = re.compile(r'^\s*Attribute\s+VB_Name\s*=\s*"([^"]+)"', re.IGNORECASE)
_IF_RE = re.compile(r'^\s*(?:If|ElseIf)\s+(.+?)\s+Then\b(.*)$', re.IGNORECASE)
_CASE_RE = re.compile(r'^\s*Case\s+(?!Else\b)(.+)$', re.IGNORECASE)
_CALL_RE = re.compile(r'\bCall\s+([A-Za-z_]\w*)\b', re.IGNORECASE)
_RUN_RE = re.compile(r'\b(?:Application\.)?Run\s+["\']([A-Za-z_]\w*)["\']', re.IGNORECASE)
_CREATE_OBJECT_RE = re.compile(r'\b(?:CreateObject|GetObject)\s*\([^\)]*["\']([^"\']+)["\']', re.IGNORECASE)
_WORKSHEET_RE = re.compile(r'\b(?:Worksheets|Sheets)\s*\(\s*["\']([^"\']+)["\']\s*\)', re.IGNORECASE)
_WORKBOOK_RE = re.compile(r'\bWorkbooks\s*\(\s*["\']([^"\']+)["\']\s*\)', re.IGNORECASE)
_PATH_RE = re.compile(r'(?P<path>(?:[A-Za-z]:\\|\\\\)[^"\']+)')
_SQL_RE = re.compile(r'\b(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|EXEC(?:UTE)?)\b', re.IGNORECASE)
_SECRET_RE = re.compile(r'(?i)(password|pwd)\s*=\s*[^;"\']+')


@dataclass(frozen=True)
class ProcedureRange:
    name: str
    kind: str
    visibility: str
    start_line: int
    end_line: int
    parameters: tuple[str, ...]


def _clean_line(line: str, limit: int = 180) -> str:
    value = line.strip()
    value = _SECRET_RE.sub(r'\1=<redacted>', value)
    return value if len(value) <= limit else f'{value[: limit - 3]}...'


def _module_kind(file_name: str) -> str:
    lower = file_name.lower()
    if lower.endswith('.cls'):
        return 'class_module'
    if lower.endswith('.frm'):
        return 'user_form'
    if lower.endswith('.bas'):
        return 'standard_module'
    return 'vba_source'


def _parse_parameters(raw: str | None) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return ()
    return tuple(part.strip() for part in raw.split(',') if part.strip())


def _procedure_for_line(procedures: list[ProcedureRange], line_no: int) -> str | None:
    for proc in procedures:
        if proc.start_line <= line_no <= proc.end_line:
            return proc.name
    return None


def _parse_procedures(lines: list[str]) -> list[ProcedureRange]:
    procedures: list[ProcedureRange] = []
    active: tuple[str, str, str, int, tuple[str, ...]] | None = None
    for line_no, line in enumerate(lines, 1):
        if active is None:
            match = _PROCEDURE_RE.match(line)
            if not match:
                continue
            visibility = (match.group(1) or 'Public').title()
            kind = re.sub(r'\s+', ' ', match.group(3)).title()
            active = (match.group(4), kind, visibility, line_no, _parse_parameters(match.group(5)))
            continue
        if _END_PROCEDURE_RE.match(line):
            name, kind, visibility, start_line, parameters = active
            procedures.append(ProcedureRange(name, kind, visibility, start_line, line_no, parameters))
            active = None
    if active is not None:
        name, kind, visibility, start_line, parameters = active
        procedures.append(ProcedureRange(name, kind, visibility, start_line, len(lines), parameters))
    return procedures


def _extract_calls(lines: list[str], proc: ProcedureRange, known_names: set[str]) -> list[str]:
    calls: set[str] = set()
    for line in lines[proc.start_line: proc.end_line]:
        code = line.split("'", 1)[0]
        for match in _CALL_RE.finditer(code):
            calls.add(match.group(1))
        for match in _RUN_RE.finditer(code):
            calls.add(match.group(1))
        for name in known_names:
            if name == proc.name:
                continue
            if re.search(rf'\b{re.escape(name)}\b', code, re.IGNORECASE):
                calls.add(name)
    return sorted(calls, key=str.lower)


def _dependency_key(item: dict[str, object]) -> tuple[object, ...]:
    return (item['type'], str(item['name']).lower(), item.get('line'))


def _extract_dependencies(lines: list[str], procedures: list[ProcedureRange]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()

    def add(dep_type: str, name: str, line_no: int) -> None:
        item = {
            'type': dep_type,
            'name': name,
            'line': line_no,
            'procedure': _procedure_for_line(procedures, line_no),
        }
        key = _dependency_key(item)
        if key not in seen:
            seen.add(key)
            items.append(item)

    for line_no, line in enumerate(lines, 1):
        code = line.split("'", 1)[0]
        for match in _CREATE_OBJECT_RE.finditer(code):
            add('com_automation', match.group(1), line_no)
        for match in _WORKSHEET_RE.finditer(code):
            add('worksheet', match.group(1), line_no)
        for match in _WORKBOOK_RE.finditer(code):
            add('workbook', match.group(1), line_no)
        path_match = _PATH_RE.search(code)
        if path_match:
            add('filesystem_path', _clean_line(path_match.group('path'), 120), line_no)
        if re.search(r'\bADODB\.(?:Connection|Command|Recordset)\b', code, re.IGNORECASE):
            add('database', 'ADODB', line_no)
        if _SQL_RE.search(code) and ('"' in code or "'" in code):
            add('sql', _SQL_RE.search(code).group(1).upper(), line_no)
        for token, name in (
            ('Outlook.Application', 'Microsoft Outlook'),
            ('Scripting.FileSystemObject', 'FileSystemObject'),
            ('MSXML2.', 'MSXML2'),
            ('WinHttp.', 'WinHTTP'),
        ):
            if token.lower() in code.lower():
                add('external_component', name, line_no)
    return items


def _extract_risks(lines: list[str], procedures: list[ProcedureRange]) -> list[dict[str, object]]:
    rules = (
        ('VBA001', 'high', 'Tratamento de erro suprimido', re.compile(r'\bOn\s+Error\s+Resume\s+Next\b', re.I)),
        ('VBA002', 'critical', 'Execução de comando do sistema', re.compile(r'\bShell\s*\(', re.I)),
        ('VBA003', 'high', 'Automação por envio de teclas', re.compile(r'\bSendKeys\b', re.I)),
        ('VBA004', 'critical', 'Possível segredo no código', _SECRET_RE),
        ('VBA005', 'medium', 'Caminho de arquivo fixo', _PATH_RE),
        ('VBA006', 'low', 'Automação frágil por Select/Activate', re.compile(r'\.(?:Select|Activate)\b', re.I)),
        ('VBA007', 'high', 'SQL montado por concatenação', re.compile(r'(?i)\b(?:SELECT|INSERT|UPDATE|DELETE|EXEC)\b.*["\']\s*&|&\s*.*\b(?:WHERE|VALUES|SET)\b')),
        ('VBA008', 'high', 'Exclusão de arquivo', re.compile(r'^\s*Kill\s+', re.I)),
        ('VBA009', 'high', 'Chamada de biblioteca nativa', re.compile(r'\bDeclare\s+(?:PtrSafe\s+)?(?:Function|Sub)\b.*\bLib\s+["\']', re.I)),
        ('VBA010', 'medium', 'Criação dinâmica de componente COM', re.compile(r'\b(?:CreateObject|GetObject)\s*\(', re.I)),
    )
    findings: list[dict[str, object]] = []
    for line_no, line in enumerate(lines, 1):
        code = line.split("'", 1)[0]
        for code_id, severity, title, pattern in rules:
            if pattern.search(code):
                findings.append(
                    {
                        'code': code_id,
                        'severity': severity,
                        'title': title,
                        'line': line_no,
                        'procedure': _procedure_for_line(procedures, line_no),
                        'evidence': _clean_line(code),
                    }
                )
    return findings


def _next_action(lines: list[str], line_no: int) -> str | None:
    for candidate in lines[line_no: min(line_no + 4, len(lines))]:
        stripped = candidate.strip()
        if not stripped or stripped.startswith("'"):
            continue
        if re.match(r'^(Else|ElseIf|End\s+If|Case|End\s+Select)\b', stripped, re.I):
            return None
        return _clean_line(stripped, 120)
    return None


def _extract_rules(
    lines: list[str], procedures: list[ProcedureRange], module_name: str
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rules: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    sequence = 0
    for line_no, line in enumerate(lines, 1):
        if_match = _IF_RE.match(line)
        case_match = _CASE_RE.match(line)
        if not if_match and not case_match:
            continue
        sequence += 1
        if if_match:
            expression = _clean_line(if_match.group(1), 160)
            inline_action = _clean_line(if_match.group(2), 120) if if_match.group(2).strip() else None
            rule_type = 'condition'
        else:
            expression = _clean_line(case_match.group(1), 160)
            inline_action = None
            rule_type = 'case'
        action = inline_action or _next_action(lines, line_no)
        procedure = _procedure_for_line(procedures, line_no)
        rule_id = f'VBA-RULE-{sequence:03d}'
        requirement_id = f'VBA-REQ-{sequence:03d}'
        if action:
            statement = f'Quando {expression}, o sistema deve executar a regra: {action}.'
            confidence = 0.72 if inline_action else 0.66
        else:
            statement = f'Quando {expression}, o sistema deve aplicar a regra definida em {procedure or module_name}.'
            confidence = 0.58
        rules.append(
            {
                'id': rule_id,
                'type': rule_type,
                'expression': expression,
                'action': action,
                'line': line_no,
                'procedure': procedure,
            }
        )
        candidates.append(
            {
                'id': requirement_id,
                'statement': statement,
                'confidence': confidence,
                'requires_human_validation': True,
                'source': {
                    'module': module_name,
                    'procedure': procedure,
                    'line': line_no,
                    'rule_id': rule_id,
                },
            }
        )
    return rules, candidates


def _modernization(risks: list[dict[str, object]], dependencies: list[dict[str, object]]) -> list[dict[str, str]]:
    risk_codes = {str(item['code']) for item in risks}
    dep_types = {str(item['type']) for item in dependencies}
    actions: list[dict[str, str]] = []
    if 'VBA004' in risk_codes:
        actions.append({'priority': 'P0', 'action': 'Remover segredos do VBA e usar cofre/identidade gerenciada.'})
    if 'VBA002' in risk_codes or 'VBA009' in risk_codes:
        actions.append({'priority': 'P0', 'action': 'Isolar comandos de sistema e chamadas nativas em serviço controlado.'})
    if 'database' in dep_types or 'sql' in dep_types:
        actions.append({'priority': 'P1', 'action': 'Separar acesso ao banco em camada parametrizada/API e remover SQL da interface Excel.'})
    if 'com_automation' in dep_types or 'external_component' in dep_types:
        actions.append({'priority': 'P1', 'action': 'Substituir automação COM por APIs suportadas quando houver equivalente.'})
    if 'filesystem_path' in dep_types:
        actions.append({'priority': 'P1', 'action': 'Externalizar caminhos por ambiente e eliminar dependência de unidade/rede fixa.'})
    if 'VBA006' in risk_codes:
        actions.append({'priority': 'P2', 'action': 'Eliminar Select/Activate e operar diretamente sobre objetos Excel.'})
    actions.append({'priority': 'P2', 'action': 'Criar testes para cada regra candidata antes de migrar ou refatorar o VBA.'})
    return actions


def analyze_vba_source(source: str, *, file_name: str = 'module.bas') -> dict[str, object]:
    normalized = source.replace('\r\n', '\n').replace('\r', '\n')
    lines = normalized.split('\n')
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    module_match = next((_MODULE_RE.match(line) for line in lines if _MODULE_RE.match(line)), None)
    module_name = module_match.group(1) if module_match else file_name.rsplit('.', 1)[0]
    procedures = _parse_procedures(lines)
    known_names = {proc.name for proc in procedures}
    procedure_payload = [
        {
            'name': proc.name,
            'kind': proc.kind,
            'visibility': proc.visibility,
            'start_line': proc.start_line,
            'end_line': proc.end_line,
            'parameters': list(proc.parameters),
            'calls': _extract_calls(lines, proc, known_names),
        }
        for proc in procedures
    ]
    dependencies = _extract_dependencies(lines, procedures)
    risks = _extract_risks(lines, procedures)
    rules, candidates = _extract_rules(lines, procedures, module_name)
    severity_counts = {name: sum(1 for item in risks if item['severity'] == name) for name in ('critical', 'high', 'medium', 'low')}
    return {
        'schema_version': SCHEMA_VERSION,
        'analyzer': ANALYZER_NAME,
        'analysis_type': 'static_only',
        'execution_performed': False,
        'automatic_incorporation': False,
        'status': 'AGUARDANDO_REVISAO_HUMANA',
        'sha256': digest,
        'module': {
            'name': module_name,
            'kind': _module_kind(file_name),
            'file_name': file_name,
            'option_explicit': any(re.match(r'^\s*Option\s+Explicit\b', line, re.I) for line in lines),
        },
        'summary': {
            'lines': len(lines),
            'procedures': len(procedures),
            'dependencies': len(dependencies),
            'business_rules': len(rules),
            'requirement_candidates': len(candidates),
            'risks': len(risks),
            'risks_by_severity': severity_counts,
        },
        'procedures': procedure_payload,
        'dependencies': dependencies,
        'business_rules': rules,
        'risks': risks,
        'requirement_candidates': candidates,
        'modernization_plan': _modernization(risks, dependencies),
    }
