import csv
import io
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.models.ai_quality import QualidadeIASnapshot
from app.models.auditoria import AuditoriaEvento
from app.models.requisito import Requisito


def _safe_pct(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((value / total) * 100.0, 2)


def _clip(score: float) -> float:
    return round(max(0.0, min(100.0, score)), 2)


def calcular_resumo_qualidade_ia(db):
    total = db.query(Requisito).count()

    aprovados = (
        db.query(Requisito)
        .filter(func.lower(Requisito.status).in_(['aprovado', 'aprovados', 'concluido', 'concluida']))
        .count()
    )
    em_analise = (
        db.query(Requisito)
        .filter(func.lower(Requisito.status).like('%analise%'))
        .count()
    )
    pendentes = max(total - aprovados, 0)

    cobertura_dados = (
        db.query(Requisito)
        .filter(func.length(func.coalesce(Requisito.descricao, '')) >= 40)
        .count()
    )

    sete_dias_atras = datetime.now(timezone.utc) - timedelta(days=7)
    acao_normalizada = func.lower(func.coalesce(AuditoriaEvento.acao, ''))
    incidentes_criticos = (
        db.query(AuditoriaEvento)
        .filter(AuditoriaEvento.criado_em >= sete_dias_atras)
        .filter(
            acao_normalizada.like('%erro%')
            | acao_normalizada.like('%falha%')
            | acao_normalizada.like('%incidente%')
            | acao_normalizada.like('%vulnerabilidade%')
        )
        .count()
    )

    aprovados_pct = _safe_pct(aprovados, total)
    em_analise_pct = _safe_pct(em_analise, total)
    cobertura_pct = _safe_pct(cobertura_dados, total)
    pendentes_pct = _safe_pct(pendentes, total)

    acuracia = _clip(45.0 + (aprovados_pct * 0.55))
    relevancia = _clip(35.0 + (aprovados_pct * 0.35) + (em_analise_pct * 0.2))
    consistencia = _clip(100.0 - (pendentes_pct * 0.75))
    seguranca = _clip(100.0 - (incidentes_criticos * 12.5))
    cobertura = _clip(30.0 + (cobertura_pct * 0.7))

    score_geral = _clip(
        (acuracia * 0.25)
        + (relevancia * 0.2)
        + (consistencia * 0.2)
        + (seguranca * 0.25)
        + (cobertura * 0.1)
    )

    if score_geral >= 85:
        status = 'excelente'
    elif score_geral >= 70:
        status = 'estavel'
    elif score_geral >= 55:
        status = 'atencao'
    else:
        status = 'critico'

    recomendacoes = []
    if cobertura < 75:
        recomendacoes.append('Aumentar detalhamento das descricoes dos requisitos para melhorar cobertura de contexto.')
    if seguranca < 80:
        recomendacoes.append('Priorizar tratamento de incidentes criticos e reforcar validacoes de seguranca.')
    if consistencia < 75:
        recomendacoes.append('Reduzir pendencias no pipeline para estabilizar consistencia operacional.')
    if not recomendacoes:
        recomendacoes.append('Manter rotina de monitoramento continuo com snapshots diarios de qualidade.')

    metricas = {
        'acuracia': acuracia,
        'relevancia': relevancia,
        'consistencia': consistencia,
        'seguranca': seguranca,
        'cobertura_dados': cobertura,
    }
    guardrail_gaps = [
        {
            'metrica': nome,
            'valor_atual': valor,
            'meta': 100.0,
            'gap': _clip(100.0 - valor),
        }
        for nome, valor in metricas.items()
        if valor < 100.0
    ]
    guardrail_passou = score_geral == 100.0 and not guardrail_gaps and incidentes_criticos == 0

    return {
        'status': status,
        'score_geral': score_geral,
        'metricas': metricas,
        'contexto': {
            'amostra_total': total,
            'aprovados': aprovados,
            'em_analise': em_analise,
            'pendentes': pendentes,
            'incidentes_criticos_7d': incidentes_criticos,
        },
        'recomendacoes': recomendacoes,
        'guardrail_100': {
            'meta_score': 100.0,
            'passou': guardrail_passou,
            'bloqueante': not guardrail_passou,
            'mensagem': (
                'Qualidade IA em 100%. Manter monitoramento continuo.'
                if guardrail_passou
                else 'Qualidade IA abaixo de 100%. Nao mascarar o score; tratar gaps antes de considerar o guard rail aprovado.'
            ),
            'gaps': guardrail_gaps,
        },
        'algoritmo': {
            'versao': '1.1.0',
            'atualizado_em': datetime.now(timezone.utc).isoformat(),
        },
    }


def registrar_snapshot_qualidade_ia(db):
    resumo = calcular_resumo_qualidade_ia(db)
    metricas = resumo['metricas']
    contexto = resumo['contexto']

    snapshot = QualidadeIASnapshot(
        score_geral=resumo['score_geral'],
        acuracia=metricas['acuracia'],
        relevancia=metricas['relevancia'],
        consistencia=metricas['consistencia'],
        seguranca=metricas['seguranca'],
        cobertura_dados=metricas['cobertura_dados'],
        incidentes_criticos=contexto['incidentes_criticos_7d'],
        amostra_total=contexto['amostra_total'],
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return {
        'id': snapshot.id,
        'criado_em': snapshot.criado_em.isoformat() if snapshot.criado_em else None,
        'score_geral': round(snapshot.score_geral, 2),
    }


def listar_tendencia(db, limit=12, dias=None):
    query = db.query(QualidadeIASnapshot)
    if dias is not None and dias > 0:
        desde = datetime.now(timezone.utc) - timedelta(days=dias)
        query = query.filter(QualidadeIASnapshot.criado_em >= desde)
    snapshots = (
        query
        .order_by(QualidadeIASnapshot.criado_em.desc())
        .limit(limit)
        .all()
    )

    items = [
        {
            'id': s.id,
            'timestamp': s.criado_em.isoformat() if s.criado_em else None,
            'score_geral': round(s.score_geral, 2),
            'acuracia': round(s.acuracia, 2),
            'relevancia': round(s.relevancia, 2),
            'consistencia': round(s.consistencia, 2),
            'seguranca': round(s.seguranca, 2),
            'cobertura_dados': round(s.cobertura_dados, 2),
            'incidentes_criticos': s.incidentes_criticos,
        }
        for s in snapshots
    ]
    items.reverse()
    return items


def exportar_tendencia_csv(itens):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'id',
        'timestamp',
        'score_geral',
        'acuracia',
        'relevancia',
        'consistencia',
        'seguranca',
        'cobertura_dados',
        'incidentes_criticos',
    ])

    for item in itens:
        writer.writerow([
            item.get('id'),
            item.get('timestamp'),
            item.get('score_geral'),
            item.get('acuracia'),
            item.get('relevancia'),
            item.get('consistencia'),
            item.get('seguranca'),
            item.get('cobertura_dados'),
            item.get('incidentes_criticos'),
        ])

    return output.getvalue()


def _pdf_escape(text: str) -> str:
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _build_simple_pdf(lines):
    content_lines = ['BT', '/F1 11 Tf', '40 800 Td']
    for line in lines:
        content_lines.append(f'({_pdf_escape(str(line))}) Tj')
        content_lines.append('T*')
    content_lines.append('ET')

    content_stream = '\n'.join(content_lines).encode('latin-1', errors='replace')

    objects = []
    objects.append(b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
    objects.append(b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n')
    objects.append(b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n')
    objects.append(b'4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n')
    objects.append(f'5 0 obj\n<< /Length {len(content_stream)} >>\nstream\n'.encode('ascii') + content_stream + b'\nendstream\nendobj\n')

    pdf = b'%PDF-1.4\n'
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj

    xref_offset = len(pdf)
    pdf += f'xref\n0 {len(objects) + 1}\n'.encode('ascii')
    pdf += b'0000000000 65535 f \n'
    for offset in offsets[1:]:
        pdf += f'{offset:010d} 00000 n \n'.encode('ascii')

    pdf += f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n'.encode('ascii')
    return pdf


def exportar_tendencia_pdf(itens):
    lines = [
        'ReqSys - Tendencia Qualidade IA',
        f'Gerado em: {datetime.now(timezone.utc).isoformat()}',
        '---',
    ]

    if not itens:
        lines.append('Sem snapshots disponiveis.')
    else:
        for item in itens:
            lines.append(
                f"{item.get('timestamp', '-')}: score={item.get('score_geral', 0)} acuracia={item.get('acuracia', 0)} seguranca={item.get('seguranca', 0)} incidentes={item.get('incidentes_criticos', 0)}"
            )

    return _build_simple_pdf(lines)
