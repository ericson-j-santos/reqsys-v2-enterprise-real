n: str) -> str:
    normalized = version.strip()
    if not _SEMVER_RE.fullmatch(normalized):
        raise GovernedVbaEvaluationError(
            'VBA_GOVERNED_VERSION_INVALID',
            'A versão deve usar Versionamento Semântico no formato X.Y.Z.',
        )
    return normalized


def _procedure_blocks(lines: list[str]) -> list[ProcedureBlock]:
    blocks: list[ProcedureBlock] = []
    active: tuple[int, re.Match[str]] | None = None
    for index, line in enumerate(lines):
        if active is None:
            match = _PROCEDURE_RE.match(line)
            if match:
                active = (index, match)
            continue
        if _END_PROCEDURE_RE.match(line):
            start, match = active
            blocks.append(
                ProcedureBlock(
                    start=start,
                    end=index,
                    kind=re.sub(r'\s+', ' ', match.group('kind')).title(),
                    name=match.group('name'),
                    indent=match.group('indent'),
                )
            )
            active = None
    if active is not None:
        raise GovernedVbaEvaluationError(
            'VBA_GOVERNED_PROCEDURE_UNTERMINATED',
            f'O procedimento iniciado na linha {active[0] + 1} não foi encerrado.',
        )
    return blocks


def _insert_option_explicit(lines: list[str]) -> tuple[list[str], bool]:
    if any(re.match(r'^\s*Option\s+Explicit\b', line, re.IGNORECASE) for line in lines):
        return list(lines), False
    position = 0
    while position < len(lines) and (
        lines[position].startswith('Attribute ') or not lines[position].strip()
    ):
        position += 1
    updated = list(lines)
    updated[position:position] = ['Option Explicit', '']
    return updated, True


def _transform_procedures(
    lines: list[str], module_name: str
) -> tuple[list[str], list[dict[str, object]]]:
    decisions: list[dict[str, object]] = []
    updated = list(lines)
    for block in reversed(_procedure_blocks(lines)):
        body = lines[block.start + 1 : block.end]
        reason: str | None = None
        if any(_ON_ERROR_RE.match(line) for line in body):
            reason = 'existing_error_handler_requires_human_review'
        elif any(_LABEL_RE.match(line) for line in body):
            reason = 'existing_labels_require_human_review'

        if reason:
            decisions.append(
                {
                    'procedure': block.name,
                    'kind': block.kind,
                    'status': 'not_applied',
                    'reason': reason,
                }
            )
            continue

        label_token = hashlib.sha256(
            f'{module_name}:{block.name}:{block.start}'.encode()
        ).hexdigest()[:10].upper()
        error_label = f'ReqSys_Error_{label_token}'
        exit_label = f'ReqSys_Exit_{label_token}'
        error_number = f'ReqSysErrNumber_{label_token}'
        error_description = f'ReqSysErrDescription_{label_token}'
        error_source = f'ReqSysErrSource_{label_token}'
        inner = f'{block.indent}    '
        entry = [
            f'{inner}Dim {error_number} As Long',
            f'{inner}Dim {error_description} As String',
            f'{inner}Dim {error_source} As String',
            f'{inner}On Error GoTo {error_label}',
        ]
        handler = [
            f'{block.indent}{exit_label}:',
            f'{inner}Exit {"Sub" if block.kind == "Sub" else "Function" if block.kind == "Function" else "Property"}',
            f'{block.indent}{error_label}:',
            f'{inner}{error_number} = Err.Number',
            f'{inner}{error_description} = Err.Description',
            f'{inner}{error_source} = Err.Source',
            f'{inner}ReqSys_LogError "{module_name}.{block.name}", {error_number}, {error_description}',
            f'{inner}Err.Raise {error_number}, {error_source}, {error_description}',
        ]
        updated[block.end:block.end] = handler
        updated[block.start + 1:block.start + 1] = entry
        decisions.append(
            {
                'procedure': block.name,
                'kind': block.kind,
                'status': 'applied',
                'controls': ['error_capture', 'execution_log', 'error_rethrow'],
            }
        )
    decisions.reverse()
    return updated, decisions


def _support_module() -> str:
    return """Attribute VB_Name = "ReqSysControls"
Option Explicit

Public Sub ReqSys_LogError(ByVal ProcedureName As String, ByVal ErrorNumber As Long, ByVal ErrorDescription As String)
    Debug.Print Format$(Now, "yyyy-mm-dd hh:nn:ss"); " | ERROR | "; ProcedureName; " | "; CStr(ErrorNumber); " | "; ErrorDescription
End Sub

Public Sub ReqSys_Require(ByVal Condition As Boolean, ByVal Message As String)
    If Not Condition Then Err.Raise vbObjectError + 513, "ReqSysControls", Message
End Sub
"""


def _semantic_signature(analysis: dict[str, object]) -> dict[str, object]:
    procedures = analysis.get('procedures', [])
    dependencies = analysis.get('dependencies', [])
    rules = analysis.get('business_rules', [])
    return {
        'procedures': sorted(
            (str(item.get('name')), str(item.get('kind')))
            for item in procedures
            if isinstance(item, dict)
        ),
        'dependencies': sorted(
            (str(item.get('type')), str(item.get('name')))
            for item in dependencies
            if isinstance(item, dict)
        ),
        'business_rules': sorted(
            (str(item.get('type')), str(item.get('expression')), str(item.get('action')))
            for item in rules
            if isinstance(item, dict)
        ),
    }


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[path])
    return output.getvalue()


def build_governed_vba_evaluation_package(
    source: str,
    *,
    file_name: str = 'module.bas',
    version: str = '0.1.0',
) -> dict[str, object]:
    safe_name = _safe_file_name(file_name)
    normalized_version = _validate_version(version)
    normalized_source = source.replace('\r\n', '\n').replace('\r', '\n')
    if not normalized_source.strip():
        raise GovernedVbaEvaluationError(
            'VBA_GOVERNED_SOURCE_EMPTY', 'O código-fonte VBA está vazio.'
        )

    original_analysis = analyze_vba_with_call_graph(normalized_source, file_name=safe_name)
    module_name = str(original_analysis['module']['name'])
    original_lines = normalized_source.split('\n')
    option_lines, option_added = _insert_option_explicit(original_lines)
    transformed_lines, procedure_decisions = _transform_procedures(
        option_lines, module_name
    )
    transformed_source = '\n'.join(transformed_lines)
    if not transformed_source.endswith('\n'):
        transformed_source += '\n'
    transformed_analysis = analyze_vba_with_call_graph(
        transformed_source, file_name=safe_name
    )

    original_signature = _semantic_signature(original_analysis)
    transformed_signature = _semantic_signature(transformed_analysis)
    signature_preserved = original_signature == transformed_signature
    all_procedures_controlled = all(
        item['status'] == 'applied' for item in procedure_decisions
    )
    static_gate_passed = signature_preserved and all_procedures_controlled

    controls = [
        {
            'id': 'VBA-CONTROL-OPTION-EXPLICIT',
            'status': 'applied' if option_added else 'already_present',
            'evidence': f'transformed/{safe_name}',
        },
        {
            'id': 'VBA-CONTROL-ERROR-LOG-RETHROW',
            'status': 'applied' if all_procedures_controlled else 'partial',
            'procedure_decisions': procedure_decisions,
            'evidence': 'controls/ReqSysControls.bas',
        },
        {
            'id': 'VBA-CONTROL-INPUT-VALIDATION',
            'status': 'requires_dynamic_domain_validation',
            'reason': 'Preconditions cannot be inferred safely from syntax alone.',
        },
        {
            'id': 'VBA-CONTROL-SECRETS',
            'status': (
                'blocked'
                if any(item.get('code') == 'VBA004' for item in original_analysis['risks'])
                else 'no_static_secret_finding'
            ),
        },
    ]
    static_evidence = {
        'gate': 'static_behavior_preservation',
        'passed': static_gate_passed,
        'source_sha256': _sha256(normalized_source.encode('utf-8')),
        'transformed_sha256': _sha256(transformed_source.encode('utf-8')),
        'semantic_signature_preserved': signature_preserved,
        'procedure_controls_complete': all_procedures_controlled,
        'execution_performed': False,
        'dynamic_equivalence_proven': False,
        'limitation': (
            'Static checks preserve the extracted procedures, dependencies and business-rule '
            'signature. They do not prove runtime equivalence in Excel or Office.'
        ),
    }
    manifest = {
        'schema_version': PACKAGE_SCHEMA_VERSION,
        'transformer_version': TRANSFORMER_VERSION,
        'package_version': normalized_version,
        'source_file': safe_name,
        'maturity': 'STATICALLY_CONTROLLED_CANDIDATE',
        'release_allowed': False,
        'static_gate_passed': static_gate_passed,
        'dynamic_validation': {
            'status': 'future_required',
            'execution_performed': False,
            'equivalence_proven': False,
        },
        'controls': controls,
        'rollback': {
            'strategy': 'restore_original_source',
            'source_sha256': static_evidence['source_sha256'],
        },
    }
    readme = f"""# Avaliação governada de VBA {normalized_version}

Este pacote foi produzido sem executar VBA, Excel ou Office.

## Conteúdo

- `original-analysis.json`: análise estática existente do ReqSys.
- `transformed/{safe_name}`: candidato com controles mecanicamente seguros.
- `controls/ReqSysControls.bas`: apoio para registro e validação explícita.
- `evidence/static-preservation.json`: comparação estática antes/depois.
- `manifest.json` e `checksums.sha256`: versão e integridade do pacote.

## Uso seguro

1. Revise cada decisão de controle e qualquer item parcial/bloqueado.
2. Importe os módulos apenas em cópia descartável do arquivo Office.
3. Execute testes dinâmicos futuros em ambiente isolado, com entradas conhecidas e comparação de saídas.
4. Não promova o candidato: `release_allowed` permanece `false` até equivalência dinâmica e validação de domínio.

## Retorno à versão anterior

Remova os módulos transformados e restaure a fonte original identificada por SHA-256 no manifesto.
"""

    files: dict[str, bytes] = {
        'README.md': readme.encode('utf-8'),
        'analysis/original-analysis.json': _canonical_json(original_analysis),
        'controls/ReqSysControls.bas': _support_module().encode('utf-8'),
        'evidence/static-preservation.json': _canonical_json(static_evidence),
        'manifest.json': _canonical_json(manifest),
        f'transformed/{safe_name}': transformed_source.encode('utf-8'),
    }
    checksum_lines = [
        f'{_sha256(files[path])}  {path}' for path in sorted(files)
    ]
    files['checksums.sha256'] = ('\n'.join(checksum_lines) + '\n').encode('utf-8')
    package = _zip_bytes(files)
    return {
        'schema_version': PACKAGE_SCHEMA_VERSION,
        'package_version': normalized_version,
        'package_file_name': f'vba-governed-evaluation-{normalized_version}.zip',
        'package_sha256': _sha256(package),
        'zip_base64': base64.b64encode(package).decode('ascii'),
        'manifest': manifest,
        'static_evidence': static_evidence,
    }
