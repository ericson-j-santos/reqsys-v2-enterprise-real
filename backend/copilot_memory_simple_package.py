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

MEMORY_HEADERS = [
    'MemoryId', 'PlannerTaskId', 'Assunto', 'Contexto', 'EstadoAtual',
    'Decisao', 'Pendencia', 'ProximoPasso', 'FonteUrl', 'DataFonte',
    'Validade', 'PlannerTitulo', 'PlannerStatus', 'PlannerPercentual',
    'PlannerPrazo', 'Versao', 'ContentHash', 'PlannerSyncStatus',
    'PlannerAppliedSignature', 'CorrelationId', 'AtualizadoEm',
]
UPDATE_HEADERS = [
    'MemoryId', 'PlannerTaskId', 'PlannerTitulo', 'PlannerStatus',
    'PlannerPercentual', 'PlannerPrazo', 'AtualizarPlanner',
    'SolicitadoPor', 'SolicitadoEm', 'ResultadoSync', 'DetalheConflito',
    'CorrelationId',
]
HISTORY_HEADERS = [
    'EventId', 'MemoryId', 'PlannerTaskId', 'Versao', 'Origem',
    'TipoEvento', 'Resumo', 'PlannerSignature', 'CorrelationId', 'CriadoEm',
]

TABLES = [
    ('Memoria', 'tbMemoriaCopilot', MEMORY_HEADERS),
    ('AtualizacoesPlanner', 'tbAtualizacoesPlanner', UPDATE_HEADERS),
    ('Historico', 'tbHistoricoCopilot', HISTORY_HEADERS),
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

FORBIDDEN_RESTRICTED = (
    'dataverse', 'power apps', 'powerapps', 'custom_copilot_memory_api',
    'copilot_memory_service_token', 'copilot_memory_api_base_url',
)


def _coluna(numero: int) -> str:
    resultado = ''
    while numero:
        numero, resto = divmod(numero - 1, 26)
        resultado = chr(65 + resto) + resultado
    return resultado


def _celula(ref: str, valor: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(valor)}</t></is></c>'


def _sheet_xml(headers: list[str]) -> str:
    ultima = _coluna(len(headers))
    cells = ''.join(_celula(f'{_coluna(i)}1', valor) for i, valor in enumerate(headers, 1))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="A1:{ultima}1"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<sheetData><row r="1">{cells}</row></sheetData>'
        '<tableParts count="1"><tablePart r:id="rId1"/></tableParts>'
        '</worksheet>'
    )


def _table_xml(table_id: int, name: str, headers: list[str]) -> str:
    ultima = _coluna(len(headers))
    columns = ''.join(
        f'<tableColumn id="{i}" name="{xml_escape(header)}"/>'
        for i, header in enumerate(headers, 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'id="{table_id}" name="{name}" displayName="{name}" ref="A1:{ultima}1" '
        'headerRowCount="1" totalsRowShown="0">'
        f'<autoFilter ref="A1:{ultima}1"/>'
        f'<tableColumns count="{len(headers)}">{columns}</tableColumns>'
        '<tableStyleInfo name="TableStyleMedium2" showFirstColumn="0" showLastColumn="0" '
        'showRowStripes="1" showColumnStripes="0"/>'
        '</table>'
    )


def _workbook_xml() -> str:
    sheets = ''.join(
        f'<sheet name="{xml_escape(sheet)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (sheet, _, _) in enumerate(TABLES, 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{sheets}</sheets><calcPr calcId="191029"/></workbook>'
    )


def _workbook_rels() -> str:
    rels = []
    for i in range(1, len(TABLES) + 1):
        rels.append(
            '<Relationship '
            f'Id="rId{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
        )
    rels.append(
        '<Relationship Id="rId4" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + ''.join(rels) + '</Relationships>'
    )


def _sheet_rels(table_id: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" '
        f'Target="../tables/table{table_id}.xml"/>'
        '</Relationships>'
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '</styleSheet>'
    )


def _content_types() -> str:
    overrides = [
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    ]
    for i in range(1, len(TABLES) + 1):
        overrides.append(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        overrides.append(
            f'<Override PartName="/xl/tables/table{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + ''.join(overrides) + '</Types>'
    )


def gerar_planilha_xlsx() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', _content_types())
        archive.writestr(
            '_rels/.rels',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>',
        )
        archive.writestr('xl/workbook.xml', _workbook_xml())
        archive.writestr('xl/_rels/workbook.xml.rels', _workbook_rels())
        archive.writestr('xl/styles.xml', _styles_xml())
        for i, (_, table_name, headers) in enumerate(TABLES, 1):
            archive.writestr(f'xl/worksheets/sheet{i}.xml', _sheet_xml(headers))
            archive.writestr(f'xl/worksheets/_rels/sheet{i}.xml.rels', _sheet_rels(i))
            archive.writestr(f'xl/tables/table{i}.xml', _table_xml(i, table_name, headers))
    return buffer.getvalue()


def gerar_configuracao() -> dict[str, Any]:
    return {
        'versao': PACKAGE_VERSION,
        'perfil': 'copilot_memory_corporativo_restrito',
        'preencher': {
            'PLANNER_PLAN_ID': 'COLE_AQUI_O_ID_DO_PLANO',
            'SHAREPOINT_OU_ONEDRIVE': 'COLE_AQUI_O_LOCAL_DA_PLANILHA',
            'SYNC_INTERVAL_MINUTES': 15,
        },
        'dependencias': ['Planner', 'Excel Online (Business)', 'SharePoint ou OneDrive', 'Power Automate'],
        'nao_requer': ['Dataverse', 'Power Apps', 'API personalizada', 'SQL Server'],
    }


def gerar_prompts_fluxos() -> str:
    blocos = []
    for i, flow in enumerate(FLOW_CONTRACTS, 1):
        acoes = '\n'.join(f'- {acao}' for acao in flow['acoes'])
        blocos.append(
            f"FLUXO {i}: {flow['nome']}\n"
            f"Crie um fluxo agendado no Power Automate. {flow['gatilho']}.\n"
            f"Use somente estas conexoes: {', '.join(flow['conexoes'])}.\n"
            f"Acoes obrigatorias:\n{acoes}\nRegra de seguranca: {flow['regra']}\n"
        )
    return '\n\n'.join(blocos)


def gerar_html_inicio() -> str:
    cards = ''.join(
        f'<li><strong>{i}. {html_escape(flow["nome"])}</strong><br>{html_escape(flow["gatilho"])}</li>'
        for i, flow in enumerate(FLOW_CONTRACTS, 1)
    )
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Copilot Memory - Iniciar</title>
<style>body{{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;line-height:1.5}}code{{background:#eee;padding:2px 5px}}.ok{{padding:12px;border:1px solid #999}}li{{margin:12px 0}}</style></head>
<body><h1>Copilot Memory corporativo</h1>
<p class="ok"><strong>Modo simplificado:</strong> sem Dataverse, sem Power Apps, sem API personalizada e sem SQL Server.</p>
<h2>Use em 4 passos</h2><ol>
<li>Envie <code>CopilotMemory.xlsx</code> para o SharePoint ou OneDrive corporativo.</li>
<li>Abra <code>configuracao/CONFIGURAR.json</code> e preencha somente o plano do Planner e o local da planilha.</li>
<li>Crie os 3 fluxos abaixo usando os arquivos em <code>powerautomate/</code> ou os textos de <code>PROMPTS_POWER_AUTOMATE.txt</code>.</li>
<li>Adicione <code>CopilotMemory.xlsx</code> como referencia do Copilot Notebook e faca o teste com uma unica tarefa.</li>
</ol><h2>Fluxos</h2><ol>{cards}</ol>
<h2>Teste de aceite</h2><p>Crie 1 tarefa no Planner. Execute Planner→Excel. Confirme uma linha em <code>tbMemoriaCopilot</code>. Depois solicite uma alteracao em <code>tbAtualizacoesPlanner</code> com <code>AtualizarPlanner=SIM</code>. Execute Excel→Planner e confirme o historico em <code>tbHistoricoCopilot</code>. Execute novamente e confirme que nao houve duplicacao.</p>
<p>O arquivo <code>AUTOTESTE.json</code> comprova a integridade estrutural do pacote gerado. O teste real do tenant deve ser feito em DEV.</p>
</body></html>'''


def validar_planilha_xlsx(xlsx: bytes) -> dict[str, Any]:
    erros: list[str] = []
    nomes_tabelas: list[str] = []
    if not zipfile.is_zipfile(BytesIO(xlsx)):
        return {'ok': False, 'erros': ['CopilotMemory.xlsx nao e um arquivo XLSX valido']}
    with zipfile.ZipFile(BytesIO(xlsx)) as archive:
        required = {'xl/workbook.xml', 'xl/tables/table1.xml', 'xl/tables/table2.xml', 'xl/tables/table3.xml'}
        faltantes = required.difference(archive.namelist())
        if faltantes:
            erros.append(f'Partes XLSX ausentes: {sorted(faltantes)}')
        for i in range(1, 4):
            texto = archive.read(f'xl/tables/table{i}.xml').decode('utf-8')
            match = re.search(r'displayName="([^"]+)"', texto)
            if match:
                nomes_tabelas.append(match.group(1))
    esperadas = [item[1] for item in TABLES]
    if nomes_tabelas != esperadas:
        erros.append(f'Tabelas encontradas {nomes_tabelas}; esperado {esperadas}')
    return {'ok': not erros, 'erros': erros, 'tabelas': nomes_tabelas}


def montar_arquivos_prontos() -> dict[str, bytes | str]:
    xlsx = gerar_planilha_xlsx()
    files: dict[str, bytes | str] = {
        'INICIAR_AQUI.html': gerar_html_inicio(),
        'CopilotMemory.xlsx': xlsx,
        'configuracao/CONFIGURAR.json': json.dumps(gerar_configuracao(), ensure_ascii=False, indent=2),
        'PROMPTS_POWER_AUTOMATE.txt': gerar_prompts_fluxos(),
    }
    for i, flow in enumerate(FLOW_CONTRACTS, 1):
        files[f'powerautomate/{i:02d}_{flow["id"]}.json'] = json.dumps(flow, ensure_ascii=False, indent=2)
    return files


def autotestar_arquivos(files: dict[str, bytes | str]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    xlsx = files.get('CopilotMemory.xlsx')
    planilha = validar_planilha_xlsx(xlsx if isinstance(xlsx, bytes) else b'')
    checks.append({'nome': 'planilha_xlsx_com_3_tabelas', 'ok': planilha['ok'], 'detalhe': planilha})

    flows = [name for name in files if name.startswith('powerautomate/') and name.endswith('.json')]
    checks.append({'nome': 'tres_fluxos', 'ok': len(flows) == 3, 'detalhe': sorted(flows)})

    texto = '\n'.join(
        value.decode('utf-8', errors='ignore') if isinstance(value, bytes) else value
        for value in files.values()
    ).lower()
    proibidos = [item for item in FORBIDDEN_RESTRICTED if item in texto]
    checks.append({'nome': 'sem_dependencias_bloqueadas', 'ok': not proibidos, 'detalhe': proibidos})

    required = {'INICIAR_AQUI.html', 'CopilotMemory.xlsx', 'configuracao/CONFIGURAR.json', 'PROMPTS_POWER_AUTOMATE.txt'}
    faltantes = sorted(required.difference(files))
    checks.append({'nome': 'arquivos_essenciais', 'ok': not faltantes, 'detalhe': faltantes})

    return {
        'versao': PACKAGE_VERSION,
        'status': 'APROVADO' if all(item['ok'] for item in checks) else 'REPROVADO',
        'checks': checks,
    }


def gerar_pacote_pronto() -> dict[str, Any]:
    files = montar_arquivos_prontos()
    resultado = autotestar_arquivos(files)
    files['AUTOTESTE.json'] = json.dumps(resultado, ensure_ascii=False, indent=2)
    hashes = []
    for path, content in sorted(files.items()):
        raw = content if isinstance(content, bytes) else content.encode('utf-8')
        hashes.append({'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)})
    return {'files': files, 'autoteste': resultado, 'hashes': hashes}
