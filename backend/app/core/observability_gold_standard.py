"""Validação da Trilha B — Observabilidade Enterprise (padrão ouro)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.otel import otel_ativo

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class PilarTrilhaB:
    codigo: str
    titulo: str
    arquivos: tuple[str, ...]
    termos: tuple[str, ...] = ()


PILARES: tuple[PilarTrilhaB, ...] = (
    PilarTrilhaB(
        'correlation_id',
        'Correlation ID ponta a ponta',
        (
            'backend/app/middleware/observability.py',
            'backend/app/core/correlation.py',
            'backend/app/core/envelope.py',
            'frontend/src/services/api.js',
        ),
        ('X-Correlation-Id', 'obter_correlation_id', 'sessionStorage'),
    ),
    PilarTrilhaB(
        'distributed_tracing',
        'Tracing distribuído OpenTelemetry',
        ('backend/app/core/otel.py',),
        ('FastAPIInstrumentor', 'reqsys.correlation_id', 'OTEL_ENABLED'),
    ),
    PilarTrilhaB(
        'feature_metrics',
        'Métricas por feature',
        ('backend/app/core/feature_metrics.py', 'backend/app/api/monitoramento_operacional.py'),
        ('reqsys_http_requests_total', 'identificar_feature'),
    ),
    PilarTrilhaB(
        'operational_analytics',
        'Analytics operacional',
        ('backend/app/api/runtime_analytics.py',),
        ('operational_telemetry', 'feature_metrics'),
    ),
    PilarTrilhaB(
        'structured_logging',
        'Logs estruturados por request',
        ('backend/app/core/telemetry.py', 'backend/app/middleware/observability.py'),
        ('log_evento', 'http.request.completed'),
    ),
)

DOC_CANONICO = 'docs/observabilidade/TRILHA_B_PADRAO_OURO.md'
TESTES = 'backend/tests/test_observability_enterprise.py'


def _arquivo_existe(relativo: str) -> bool:
    return (ROOT / relativo).is_file()


def _arquivo_contem_termos(relativo: str, termos: tuple[str, ...]) -> bool:
    if not termos:
        return True
    caminho = ROOT / relativo
    if not caminho.is_file():
        return False
    conteudo = caminho.read_text(encoding='utf-8')
    return all(termo in conteudo for termo in termos)


def _avaliar_pilar(pilar: PilarTrilhaB) -> dict[str, Any]:
    arquivos_ok = [_arquivo_existe(arquivo) for arquivo in pilar.arquivos]
    termos_ok = [_arquivo_contem_termos(arquivo, pilar.termos) for arquivo in pilar.arquivos if pilar.termos]
    score_arquivos = round((sum(arquivos_ok) / len(arquivos_ok)) * 100) if arquivos_ok else 0
    score_termos = round((sum(termos_ok) / len(termos_ok)) * 100) if termos_ok else 100
    score = round((score_arquivos + score_termos) / 2)
    if score >= 100:
        status = 'passed'
    elif score >= 70:
        status = 'partial'
    else:
        status = 'missing'
    return {
        'codigo': pilar.codigo,
        'titulo': pilar.titulo,
        'status': status,
        'score': score,
        'arquivos_presentes': sum(arquivos_ok),
        'arquivos_total': len(arquivos_ok),
        'evidencias': list(pilar.arquivos),
    }


def avaliar_trilha_b() -> dict[str, Any]:
    pilares = [_avaliar_pilar(pilar) for pilar in PILARES]
    doc_ok = _arquivo_existe(DOC_CANONICO)
    testes_ok = _arquivo_existe(TESTES)
    score_pilares = round(sum(pilar['score'] for pilar in pilares) / len(pilares)) if pilares else 0
    bonus = 0
    if doc_ok:
        bonus += 5
    if testes_ok:
        bonus += 5
    score = min(100, score_pilares + bonus)
    blockers = [pilar['codigo'] for pilar in pilares if pilar['status'] == 'missing']
    if not doc_ok:
        blockers.append('documentacao_canonica')
    if score >= 95 and not blockers:
        status = 'passed'
    elif score >= 75:
        status = 'partial'
    else:
        status = 'missing'
    return {
        'schema_version': '1.0.0',
        'trilha': 'B',
        'nome': 'Observabilidade Enterprise',
        'padrao_ouro': True,
        'status': status,
        'score': score,
        'environment': settings.normalized_environment,
        'opentelemetry_ativo': otel_ativo(),
        'pillars': pilares,
        'documentacao_canonica': DOC_CANONICO if doc_ok else None,
        'testes': TESTES if testes_ok else None,
        'blockers': blockers,
        'guardrails': [
            'no_secrets_in_logs',
            'correlation_id_obrigatorio',
            'metricas_por_feature',
            'analytics_operacional',
        ],
        'operator_action': (
            'Trilha B em padrão ouro — manter middleware, métricas e analytics antes de novas frentes.'
            if status == 'passed'
            else 'Completar pilares em blockers antes de declarar observabilidade enterprise pronta.'
        ),
    }
