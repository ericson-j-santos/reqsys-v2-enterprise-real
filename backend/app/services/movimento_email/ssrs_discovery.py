"""Descoberta segura da origem SQL Server a partir de definições SSRS RDL/RDS.

Nunca retorna usuário, senha ou a connection string integral. O objetivo é
reduzir a ação do DBA a criar/autorizar a identidade técnica após o ReqSys
identificar servidor, banco e objetos SQL candidatos.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

_SERVER_PATTERN = re.compile(r'(?i)(?:^|;)\s*(?:data\s+source|server|address|addr|network\s+address)\s*=\s*([^;]+)')
_DATABASE_PATTERN = re.compile(r'(?i)(?:^|;)\s*(?:initial\s+catalog|database)\s*=\s*([^;]+)')
_CREDENTIAL_PATTERN = re.compile(r'(?i)(?:^|;)\s*(?:uid|user\s+id|user|pwd|password)\s*=')
_SQL_OBJECT_PATTERN = re.compile(
    r'(?i)\b(?:from|join|update|into|exec(?:ute)?)\s+'
    r'((?:\[[^\]]+\]|[#@\w$]+)(?:\.(?:\[[^\]]+\]|[#@\w$]+)){0,3})'
)


def _local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _texto_descendente(elemento: ET.Element, nome: str) -> str:
    for filho in elemento.iter():
        if _local_name(filho.tag) == nome and filho.text:
            return filho.text.strip()
    return ''


def _valor_conn(pattern: re.Pattern[str], connection_string: str) -> str:
    match = pattern.search(connection_string or '')
    if not match:
        return ''
    return match.group(1).strip().strip("\"'")


def _normalizar_objeto_sql(valor: str) -> str:
    return '.'.join(parte.strip('[]') for parte in valor.strip().split('.'))


def extrair_objetos_sql(command_text: str) -> list[str]:
    objetos = {_normalizar_objeto_sql(match.group(1)) for match in _SQL_OBJECT_PATTERN.finditer(command_text or '')}
    return sorted(objeto for objeto in objetos if objeto)


def analisar_definicao_ssrs(caminho: Path) -> dict[str, Any]:
    raiz = ET.parse(caminho).getroot()
    fontes: list[dict[str, Any]] = []
    datasets: list[dict[str, Any]] = []

    for elemento in raiz.iter():
        if _local_name(elemento.tag) != 'DataSource':
            continue
        nome = elemento.attrib.get('Name', '')
        referencia = _texto_descendente(elemento, 'DataSourceReference')
        connection_string = _texto_descendente(elemento, 'ConnectString')
        if not (nome or referencia or connection_string):
            continue
        fontes.append(
            {
                'nome': nome,
                'referencia_compartilhada': referencia or None,
                'provider': _texto_descendente(elemento, 'DataProvider') or None,
                'servidor': _valor_conn(_SERVER_PATTERN, connection_string) or None,
                'banco': _valor_conn(_DATABASE_PATTERN, connection_string) or None,
                'integrated_security': (_texto_descendente(elemento, 'IntegratedSecurity') or None),
                'credencial_embutida_detectada': bool(_CREDENTIAL_PATTERN.search(connection_string or '')),
            }
        )

    for elemento in raiz.iter():
        if _local_name(elemento.tag) != 'DataSet':
            continue
        nome = elemento.attrib.get('Name', '')
        command_text = _texto_descendente(elemento, 'CommandText')
        datasets.append(
            {
                'nome': nome,
                'data_source_name': _texto_descendente(elemento, 'DataSourceName') or None,
                'objetos_sql_candidatos': extrair_objetos_sql(command_text),
            }
        )

    return {
        'arquivo': str(caminho),
        'tipo': caminho.suffix.lower().lstrip('.'),
        'fontes': fontes,
        'datasets': datasets,
    }


def gerar_molde_dsn(*, servidor: str | None, banco: str | None) -> str | None:
    if not servidor or not banco:
        return None
    return (
        'Driver={ODBC Driver 18 for SQL Server};'
        f'Server={servidor};Database={banco};'  # placeholder seguro: somente servidor e banco, sem credenciais
        'Encrypt=yes;TrustServerCertificate=no;Authentication=<DEFINIR_COM_DBA>'
    )


def descobrir_origem_ssrs(caminho: Path) -> dict[str, Any]:
    caminho = caminho.expanduser().resolve()
    if not caminho.exists():
        raise FileNotFoundError(f'caminho SSRS não encontrado: {caminho}')

    arquivos = [caminho] if caminho.is_file() else sorted(
        [*caminho.rglob('*.rdl'), *caminho.rglob('*.rds')],
        key=lambda item: str(item).lower(),
    )
    analisados = [analisar_definicao_ssrs(arquivo) for arquivo in arquivos]

    servidores = sorted({fonte['servidor'] for item in analisados for fonte in item['fontes'] if fonte.get('servidor')})
    bancos = sorted({fonte['banco'] for item in analisados for fonte in item['fontes'] if fonte.get('banco')})
    objetos = sorted({objeto for item in analisados for ds in item['datasets'] for objeto in ds['objetos_sql_candidatos']})
    referencias = sorted({fonte['referencia_compartilhada'] for item in analisados for fonte in item['fontes'] if fonte.get('referencia_compartilhada')})

    servidor_unico = servidores[0] if len(servidores) == 1 else None
    banco_unico = bancos[0] if len(bancos) == 1 else None

    return {
        'arquivos_analisados': len(analisados),
        'servidores': servidores,
        'bancos': bancos,
        'objetos_sql_candidatos': objetos,
        'data_sources_compartilhados_pendentes': referencias,
        'dsn_molde_sem_credenciais': gerar_molde_dsn(servidor=servidor_unico, banco=banco_unico),
        'credencial_exposta_no_resultado': False,
        'detalhes': analisados,
    }