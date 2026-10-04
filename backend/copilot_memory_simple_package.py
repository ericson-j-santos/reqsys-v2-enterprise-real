from __future__ import annotations

import hashlib
import json
import re
import zipfile
from html import escape as html_escape
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape as xml_escape

PACKAGE_VERSION = '1.0.0'

TABLES = [
    ('Memoria', 'tbMemoriaCopilot', [
        'MemoryId', 'PlannerTaskId', 'Assunto', 'Contexto', 'EstadoAtual', 'Decisao',
        'Pendencia', 'ProximoPasso', 'FonteUrl', 'DataFonte', 'Validade', 'PlannerTitulo',
        'PlannerStatus', 'PlannerPercentual', 'PlannerPrazo', 'Versao', 'ContentHash',
        'PlannerSyncStatus', 'PlannerAppliedSignature', 'CorrelationId', 'AtualizadoEm',
    ]),
    ('AtualizacoesPlanner', 'tbAtualizacoesPlanner', [
        'MemoryId', 'PlannerTaskId', 'PlannerTitulo', 'PlannerStatus', 'PlannerPercentual',
        'PlannerPrazo', 'AtualizarPlanner', 'SolicitadoPor', 'SolicitadoEm', 'ResultadoSync',
        'DetalheConflito', 'CorrelationId',
    ]),
    ('Historico', 'tbHistoricoCopilot', [
        'EventId', 'MemoryId', 'PlannerTaskId', 'Versao', 'Origem', 'TipoEvento', 'Resumo',
        'PlannerSignature', 'CorrelationId', 'CriadoEm',
    ]),
]

FLOW_CONTRACTS = [
    {
        'id': 'flow_planner_to_excel_memory',
        'nome': 'Copilot Memory Restrito - Planner para Excel',
        'gatilho': 'Recorrencia a cada 15 minutos',
        'conexoes': ['Planner', 'Excel Online (Business)', 'SharePoint'],
        'acoes': [
            'Listar tarefas do plano configurado.',
            'Normalizar PlannerTaskId, titulo, status, percentual e prazo.',
            'Montar PlannerSignature deterministica.',
            'Localizar tbMemoriaCopilot por PlannerTaskId.',
            'Inserir se ausente sem sobrescrever campos de memoria humana.',
            'Se houver comando pendente e assinatura divergente, marcar CONFLITO.',
            'Em mudanca valida, incrementar Versao e acrescentar tbHistoricoCopilot.',
        ],
        'regra': 'PlannerTaskId + PlannerSignature; nunca marcar AtualizarPlanner=SIM.',
    },
    {
        'id': 'flow_excel_to_planner_restrito',
        'nome': 'Copilot Memory Restrito - Excel para Planner',
        'gatilho': 'Recorrencia a cada 15 minutos',
        'conexoes': ['Excel Online (Business)', 'SharePoint', 'Planner'],
        'acoes': [
            'Ler tbAtualizacoesPlanner e filtrar AtualizarPlanner=SIM.',
            'Reler a tarefa atual do Planner antes de escrever.',
            'Comparar assinatura atual com PlannerAppliedSignature.',
            'Se divergir, marcar CONFLITO e nao atualizar o Planner.',
            'Se igual, atualizar somente campos autorizados.',
            'Atualizar assinatura, limpar AtualizarPlanner e registrar historico.',
        ],
        'regra': 'Conflito bloqueia escrita; nunca aplicar ultimo-vence.',
    },
    {
        'id': 'flow_memory_health_restrito',
        'nome': 'Copilot Memory Restrito - Saude',
        'gatilho': 'Recorrencia a cada 60 minutos',
        'conexoes': ['Excel Online (Business)', 'SharePoint'],
        'acoes': [
            'Contar registros com PlannerSyncStatus=CONFLITO ou ERRO.',
            'Registrar CorrelationId da execucao no historico.',
            'Falhar de forma visivel quando houver conflito ou erro acima do limite.',
        ],
        'regra': 'Somente leitura/registro; nunca altera tarefa do Planner.',
    },
]

FORBIDDEN_TECHNICAL = (
    'custom_copilot_memory_api', 'copilot_memory_service_token',
    'copilot_memory_api_base_url', 'shared_commondataserviceforapps',
)


def _column(index: int) -> str:
    value = ''
    while index:
        index, remainder = divmod(index - 1, 26)
        value = chr(65 + remainder) + value
    return value


def _sheet_xml(headers: list[str]) -> str:
    cells = ''.join(
        f'<c r="{_column(i)}1" t="inlineStr"><is><t>{xml_escape(value)}</t></is></c>'
        for i, value in enumerate(headers, 1)
    )
    end = _column(len(headers))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="A1:{end}1"/><sheetData><row r="1">{cells}</row></sheetData>'
        '<tableParts count="1"><tablePart r:id="rId1"/></tableParts></worksheet>'
    )


def _table_xml(table_id: int, name: str, headers: list[str]) -> str:
    end = _column(len(headers))
    columns = ''.join(
        f'<tableColumn id="{i}" name="{xml_escape(value)}"/>'
        for i, value in enumerate(headers, 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'id="{table_id}" name="{name}" displayName="{name}" ref="A1:{end}1" '
        f'headerRowCount="1" totalsRowShown="0"><autoFilter ref="A1:{end}1"/>'
        f'<tableColumns count="{len(headers)}">{columns}</tableColumns>'
        '<tableStyleInfo name="TableStyleMedium2" showFirstColumn="0" showLastColumn="0" '
        'showRowStripes="1" showColumnStripes="0"/></table>'
    )


def _core_properties_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:creator>ReqSys</dc:creator><cp:lastModifiedBy>ReqSys</cp:lastModifiedBy>'
        '</cp:coreProperties>'
    )


def _app_properties_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>ReqSys</Application></Properties>'
    )


_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _escrever(archive: zipfile.ZipFile, path: str, content: str) -> None:
    """Grava a parte com carimbo de tempo fixo.

    Sem isso o mesmo pacote gera bytes diferentes a cada execucao, e o template
    versionado do WSJF nao poderia ser comparado com o gerador em CI.
    """
    info = zipfile.ZipInfo(path, date_time=_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, content)


def gerar_planilha_xlsx(tables: list[tuple[str, str, list[str]]] | None = None) -> bytes:
    """Gera um .xlsx minimo, valido tambem para o motor Excel do Microsoft Graph.

    As partes docProps/core.xml e docProps/app.xml sao obrigatorias para o
    Graph (nao so para o Excel desktop): um pacote OOXML sem elas abre
    normalmente no Excel local mas falha no Graph com
    'FileCorruptTryRepair'/'unsupportedWorkbook' ao tentar ler o workbook
    via API — confirmado em DEV com o WSJF.xlsx gerado antes desse fix.
    """
    tables = tables if tables is not None else TABLES
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        overrides = [
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
        ]
        sheets = []
        rels = []
        for i, (sheet, table, headers) in enumerate(tables, 1):
            overrides += [
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
                f'<Override PartName="/xl/tables/table{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"/>',
            ]
            sheets.append(f'<sheet name="{xml_escape(sheet)}" sheetId="{i}" r:id="rId{i}"/>')
            rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
            _escrever(archive, f'xl/worksheets/sheet{i}.xml', _sheet_xml(headers))
            _escrever(archive,
                f'xl/worksheets/_rels/sheet{i}.xml.rels',
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" Target="../tables/table{i}.xml"/>'
                '</Relationships>',
            )
            _escrever(archive, f'xl/tables/table{i}.xml', _table_xml(i, table, headers))
        _escrever(archive,
            '[Content_Types].xml',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>' + ''.join(overrides) + '</Types>',
        )
        _escrever(archive,
            '_rels/.rels',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            '</Relationships>',
        )
        _escrever(archive, 'docProps/core.xml', _core_properties_xml())
        _escrever(archive, 'docProps/app.xml', _app_properties_xml())
        _escrever(archive,
            'xl/workbook.xml',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{"".join(sheets)}</sheets></workbook>',
        )
        rels.append('<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
        _escrever(archive,
            'xl/_rels/workbook.xml.rels',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + ''.join(rels) + '</Relationships>',
        )
        _escrever(archive,
            'xl/styles.xml',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        )
    return buffer.getvalue()


def gerar_prompts_fluxos() -> str:
    sections = []
    for index, flow in enumerate(FLOW_CONTRACTS, 1):
        actions = '\n'.join(f'- {action}' for action in flow['acoes'])
        sections.append(
            f"FLUXO {index}: {flow['nome']}\nCrie um fluxo agendado no Power Automate. "
            f"{flow['gatilho']}. Use somente: {', '.join(flow['conexoes'])}.\n"
            f"Acoes obrigatorias:\n{actions}\nRegra: {flow['regra']}\n"
        )
    return '\n\n'.join(sections)


def gerar_html_inicio() -> str:
    items = ''.join(
        f'<li><strong>{index}. {html_escape(flow["nome"])}</strong> — {html_escape(flow["gatilho"])}</li>'
        for index, flow in enumerate(FLOW_CONTRACTS, 1)
    )
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Copilot Memory</title><style>body{{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;line-height:1.55}}code{{background:#eee;padding:2px 5px}}li{{margin:12px 0}}</style></head><body><h1>Copilot Memory — modo corporativo simples</h1><p><strong>Sem Dataverse, Power Apps, API personalizada ou SQL Server.</strong></p><h2>Use em 4 passos</h2><ol><li>Envie <code>CopilotMemory.xlsx</code> para SharePoint ou OneDrive.</li><li>Preencha <code>configuracao/CONFIGURAR.json</code>.</li><li>Crie os 3 fluxos usando <code>PROMPTS_POWER_AUTOMATE.txt</code> ou os JSONs de <code>powerautomate/</code>.</li><li>Adicione a planilha ao Copilot Notebook e teste com uma unica tarefa.</li></ol><h2>Fluxos</h2><ol>{items}</ol><h2>Teste de aceite</h2><p>Crie 1 tarefa no Planner, rode Planner→Excel, confirme uma linha em <code>tbMemoriaCopilot</code>, solicite uma alteracao em <code>tbAtualizacoesPlanner</code> com <code>AtualizarPlanner=SIM</code>, rode Excel→Planner e confirme o evento em <code>tbHistoricoCopilot</code>. Execute novamente e confirme ausencia de duplicidade.</p><p><code>AUTOTESTE.json</code> valida a estrutura do pacote. A conexao real com o tenant deve ser validada em DEV.</p></body></html>'''


def validar_planilha_xlsx(xlsx: bytes) -> dict[str, Any]:
    errors: list[str] = []
    tables: list[str] = []
    if not zipfile.is_zipfile(BytesIO(xlsx)):
        return {'ok': False, 'erros': ['CopilotMemory.xlsx invalido'], 'tabelas': []}
    with zipfile.ZipFile(BytesIO(xlsx)) as archive:
        for index in range(1, 4):
            path = f'xl/tables/table{index}.xml'
            if path not in archive.namelist():
                errors.append(f'Ausente: {path}')
                continue
            match = re.search(r'displayName="([^"]+)"', archive.read(path).decode('utf-8'))
            if match:
                tables.append(match.group(1))
    expected = [item[1] for item in TABLES]
    if tables != expected:
        errors.append(f'Tabelas {tables}; esperado {expected}')
    return {'ok': not errors, 'erros': errors, 'tabelas': tables}


def montar_arquivos_prontos() -> dict[str, bytes | str]:
    files: dict[str, bytes | str] = {
        'INICIAR_AQUI.html': gerar_html_inicio(),
        'CopilotMemory.xlsx': gerar_planilha_xlsx(),
        'configuracao/CONFIGURAR.json': json.dumps({
            'versao': PACKAGE_VERSION,
            'perfil': 'copilot_memory_corporativo_restrito',
            'preencher': {
                'PLANNER_PLAN_ID': 'COLE_AQUI_O_ID_DO_PLANO',
                'SHAREPOINT_OU_ONEDRIVE': 'COLE_AQUI_O_LOCAL_DA_PLANILHA',
                'SYNC_INTERVAL_MINUTES': 15,
            },
            'dependencias': ['Planner', 'Excel Online (Business)', 'SharePoint ou OneDrive', 'Power Automate'],
            'nao_requer': ['Dataverse', 'Power Apps', 'API personalizada', 'SQL Server'],
        }, ensure_ascii=False, indent=2),
        'PROMPTS_POWER_AUTOMATE.txt': gerar_prompts_fluxos(),
    }
    for index, flow in enumerate(FLOW_CONTRACTS, 1):
        files[f'powerautomate/{index:02d}_{flow["id"]}.json'] = json.dumps(flow, ensure_ascii=False, indent=2)
    return files


def autotestar_arquivos(files: dict[str, bytes | str]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    xlsx = files.get('CopilotMemory.xlsx')
    sheet_check = validar_planilha_xlsx(xlsx if isinstance(xlsx, bytes) else b'')
    checks.append({'nome': 'planilha_xlsx_com_3_tabelas', 'ok': sheet_check['ok'], 'detalhe': sheet_check})
    flows = sorted(name for name in files if name.startswith('powerautomate/') and name.endswith('.json'))
    checks.append({'nome': 'tres_fluxos', 'ok': len(flows) == 3, 'detalhe': flows})
    technical_text = '\n'.join(
        value.decode('utf-8', errors='ignore') if isinstance(value, bytes) else value
        for name, value in files.items()
        if name.startswith('powerautomate/') or name.startswith('configuracao/')
    ).lower()
    forbidden = [token for token in FORBIDDEN_TECHNICAL if token in technical_text]
    checks.append({'nome': 'sem_dependencias_tecnicas_bloqueadas', 'ok': not forbidden, 'detalhe': forbidden})
    required = {'INICIAR_AQUI.html', 'CopilotMemory.xlsx', 'configuracao/CONFIGURAR.json', 'PROMPTS_POWER_AUTOMATE.txt'}
    missing = sorted(required.difference(files))
    checks.append({'nome': 'arquivos_essenciais', 'ok': not missing, 'detalhe': missing})
    return {'versao': PACKAGE_VERSION, 'status': 'APROVADO' if all(check['ok'] for check in checks) else 'REPROVADO', 'checks': checks}


def gerar_pacote_pronto() -> dict[str, Any]:
    files = montar_arquivos_prontos()
    result = autotestar_arquivos(files)
    files['AUTOTESTE.json'] = json.dumps(result, ensure_ascii=False, indent=2)
    hashes = []
    for path, content in sorted(files.items()):
        raw = content if isinstance(content, bytes) else content.encode('utf-8')
        hashes.append({'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)})
    return {'files': files, 'autoteste': result, 'hashes': hashes}
