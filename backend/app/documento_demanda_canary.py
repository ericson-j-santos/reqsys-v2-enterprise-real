from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import requests

from app.core.config import settings
from app.core.security import criar_token

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 25
TIPOS_GATILHOS = {
    'POSSIVEL_REQUISITO': ('deve ', 'deverá ', 'precisa ', 'necessário ', 'obrigatório '),
    'POSSIVEL_REGRA_NEGOCIO': ('somente ', 'apenas ', 'não pode ', 'proibido ', 'permitido '),
    'POSSIVEL_REQUISITO_NAO_FUNCIONAL': ('segundo', 'até ', 'ms', 'disponibilidade', 'latência'),
}


def _falhar(mensagem: str) -> None:
    raise RuntimeError(mensagem)


def _baixar_pdf(url: str, destino: Path) -> tuple[str, int]:
    total = 0
    digest = hashlib.sha256()
    with requests.get(url, stream=True, timeout=(20, 120), allow_redirects=True) as resposta:
        resposta.raise_for_status()
        with destino.open('wb') as arquivo:
            for bloco in resposta.iter_content(chunk_size=64 * 1024):
                if not bloco:
                    continue
                total += len(bloco)
                if total > MAX_BYTES:
                    _falhar('CANARY_SAMPLE_TOO_LARGE')
                digest.update(bloco)
                arquivo.write(bloco)
    if total == 0:
        _falhar('CANARY_SAMPLE_EMPTY')
    return digest.hexdigest(), total


def _paginas_pdf(caminho: Path) -> int:
    processo = subprocess.run(
        ['pdfinfo', str(caminho)],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    for linha in processo.stdout.splitlines():
        if linha.startswith('Pages:'):
            paginas = int(linha.split(':', 1)[1].strip())
            if paginas > MAX_PAGES:
                _falhar(f'CANARY_SAMPLE_TOO_MANY_PAGES:{paginas}')
            return paginas
    _falhar('CANARY_SAMPLE_PAGES_UNKNOWN')
    return 0


def _cabecalhos(token: str, correlation_id: str | None = None) -> dict[str, str]:
    headers = {'Authorization': f'Bearer {token}'}
    if correlation_id:
        headers['X-Correlation-Id'] = correlation_id
    return headers


def _validar_ambiente() -> None:
    if settings.normalized_environment not in {'desenvolvimento', 'testes'}:
        _falhar(f'CANARY_ENVIRONMENT_FORBIDDEN:{settings.normalized_environment}')
    if (os.getenv('DOCUMENTO_DEMANDA_OCR_ENABLED') or '').strip().lower() != 'true':
        _falhar('CANARY_OCR_FLAG_DISABLED')


def executar(*, sample_url: str, sample_source: str, run_id: str) -> dict[str, object]:
    _validar_ambiente()
    token = criar_token({'sub': 'reqsys-ocr-canary', 'papel': 'admin'}, minutos=10)
    api_url = 'http://127.0.0.1:8000'

    readiness = requests.get(
        f'{api_url}/v1/ocr/demandas/documentos/ocr-readiness',
        headers=_cabecalhos(token),
        timeout=30,
    )
    readiness.raise_for_status()
    readiness_data = readiness.json()['data']
    if readiness_data.get('enabled') is not True or readiness_data.get('ready') is not True:
        _falhar(f'CANARY_OCR_NOT_READY:{readiness_data}')

    with tempfile.TemporaryDirectory(prefix='reqsys_canary_ocr_') as diretorio:
        caminho = Path(diretorio) / 'sample.pdf'
        sha256, bytes_total = _baixar_pdf(sample_url, caminho)
        paginas = _paginas_pdf(caminho)
        demanda_ref = f'CANARY-OCR-DEV-{run_id}'
        correlation_id = f'OCR-CANARY-{run_id}'

        with caminho.open('rb') as arquivo:
            primeira = requests.post(
                f'{api_url}/v1/ocr/demandas/documentos/analisar',
                headers=_cabecalhos(token, correlation_id),
                data={'demanda_ref': demanda_ref},
                files={'arquivo': ('sample.pdf', arquivo, 'application/pdf')},
                timeout=600,
            )
        primeira.raise_for_status()
        primeira_data = primeira.json()['data']

        with caminho.open('rb') as arquivo:
            repeticao = requests.post(
                f'{api_url}/v1/ocr/demandas/documentos/analisar',
                headers=_cabecalhos(token, f'{correlation_id}-RETRY'),
                data={'demanda_ref': demanda_ref},
                files={'arquivo': ('sample.pdf', arquivo, 'application/pdf')},
                timeout=600,
            )
        repeticao.raise_for_status()
        repeticao_data = repeticao.json()['data']

    candidatos = primeira_data.get('candidatos') or []
    if primeira_data.get('status') != 'AGUARDANDO_REVISAO_HUMANA':
        _falhar(f"CANARY_UNEXPECTED_STATUS:{primeira_data.get('status')}")
    if primeira_data.get('incorporacao_automatica') is not False:
        _falhar('CANARY_AUTOMATIC_INCORPORATION_FORBIDDEN')
    if not candidatos:
        _falhar('CANARY_NO_CANDIDATES')
    if not all(item.get('requer_validacao_humana') is True for item in candidatos):
        _falhar('CANARY_HUMAN_REVIEW_NOT_REQUIRED_FOR_ALL')
    if repeticao_data.get('id') != primeira_data.get('id') or repeticao_data.get('idempotente') is not True:
        _falhar('CANARY_IDEMPOTENCY_FAILED')

    inconsistentes = 0
    for item in candidatos:
        gatilhos = TIPOS_GATILHOS.get(str(item.get('tipo')), ())
        texto = str(item.get('texto') or '').lower()
        if gatilhos and not any(gatilho in texto for gatilho in gatilhos):
            inconsistentes += 1

    total = len(candidatos)
    return {
        'schema_version': '1.0.0',
        'environment': settings.normalized_environment,
        'sample': {
            'source': sample_source,
            'url': sample_url,
            'sha256': sha256,
            'bytes': bytes_total,
            'pages': paginas,
            'classification': 'HOMOLOGATED_APPROVED',
            'contains_personal_data': False,
            'approval_reference': 'user-request-2026-08-26',
        },
        'readiness': {
            'enabled': readiness_data.get('enabled'),
            'ready': readiness_data.get('ready'),
        },
        'analysis_id': primeira_data.get('id'),
        'status': primeira_data.get('status'),
        'extraction_success': True,
        'candidates_total': total,
        'candidate_types': dict(Counter(str(item.get('tipo')) for item in candidatos)),
        'candidate_with_page_rate': round(sum(item.get('pagina') is not None for item in candidatos) / total, 4),
        'human_review_required_rate': round(sum(item.get('requer_validacao_humana') is True for item in candidatos) / total, 4),
        'automatic_incorporation': primeira_data.get('incorporacao_automatica'),
        'idempotent_retry': True,
        'trigger_consistency_rate': round((total - inconsistentes) / total, 4),
        'semantic_false_positive_rate': None,
        'semantic_false_positive_status': 'REQUIRES_HUMAN_LABELING',
        'stg_touched': False,
        'prod_touched': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample-url', required=True)
    parser.add_argument('--sample-source', required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    report = executar(sample_url=args.sample_url, sample_source=args.sample_source, run_id=args.run_id)
    payload = base64.urlsafe_b64encode(json.dumps(report, ensure_ascii=False).encode('utf-8')).decode('ascii')
    print(f'REQSYS_CANARY_REPORT_B64={payload}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
