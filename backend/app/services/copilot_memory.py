"""Memória persistente do Copilot e sincronização governada Planner/Excel.

O ReqSys é a fonte da memória e do histórico. O Planner continua sendo a fonte
operacional das tarefas e o Excel/SharePoint é uma projeção tabular para
consulta pelo Copilot Notebook.

Prevenção de loop:
- conteúdo é versionado por SHA-256 e origem não entra no hash;
- Planner confirma o hash aplicado sem gerar uma nova versão;
- Excel só gera comando para Planner com `atualizar_planner=true`;
- comando só é emitido quando o hash desejado difere do último hash confirmado;
- alteração concorrente no Planner durante comando pendente vira `conflito`.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.copilot_memory import CopilotMemoryHistory, CopilotMemoryRecord

STATUS_NAO_SOLICITADO = 'nao_solicitado'
STATUS_PENDENTE = 'pendente'
STATUS_SINCRONIZADO = 'sincronizado'
STATUS_ERRO = 'erro'
STATUS_CONFLITO = 'conflito'

_CAMPOS_MEMORIA = (
    'assunto',
    'contexto',
    'estado_atual',
    'decisao',
    'pendencia',
    'proximo_passo',
    'fonte_url',
    'data_fonte',
    'validade',
)
_CAMPOS_PLANNER = (
    'planner_titulo',
    'planner_status',
    'planner_percentual',
    'planner_prazo',
)
_CAMPOS_CONTEUDO = ('planner_task_id',) + _CAMPOS_MEMORIA + _CAMPOS_PLANNER


def _texto(valor: Any) -> str:
    return str(valor or '').strip()


def _hash_json(valor: dict[str, Any]) -> str:
    bruto = json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(bruto.encode('utf-8')).hexdigest()


def _gerar_memory_id(planner_task_id: str) -> str:
    digest = hashlib.sha256(planner_task_id.encode('utf-8')).hexdigest()[:24]
    return f'planner-{digest}'


def _planner_hash(snapshot: dict[str, Any]) -> str:
    return _hash_json({campo: snapshot.get(campo, '') for campo in _CAMPOS_PLANNER})


def _content_hash(snapshot: dict[str, Any]) -> str:
    return _hash_json({campo: snapshot.get(campo, '') for campo in _CAMPOS_CONTEUDO})


def _base_snapshot(record: CopilotMemoryRecord | None) -> dict[str, Any]:
    if record is None:
        return {
            'planner_task_id': None,
            'assunto': '',
            'contexto': '',
            'estado_atual': '',
            'decisao': '',
            'pendencia': '',
            'proximo_passo': '',
            'fonte_url': '',
            'data_fonte': '',
            'validade': 'ativa',
            'planner_titulo': '',
            'planner_status': '',
            'planner_percentual': 0,
            'planner_prazo': '',
        }
    return {campo: getattr(record, campo) for campo in _CAMPOS_CONTEUDO}


def _montar_snapshot(payload: dict[str, Any], record: CopilotMemoryRecord | None) -> dict[str, Any]:
    snapshot = _base_snapshot(record)

    if payload.get('planner_task_id') is not None:
        snapshot['planner_task_id'] = _texto(payload['planner_task_id']) or None

    for campo in _CAMPOS_MEMORIA:
        if payload.get(campo) is not None:
            snapshot[campo] = _texto(payload[campo])

    for campo in _CAMPOS_PLANNER:
        if payload.get(campo) is None:
            continue
        if campo == 'planner_percentual':
            snapshot[campo] = int(payload[campo])
        else:
            snapshot[campo] = _texto(payload[campo])

    if not snapshot['assunto'] and snapshot['planner_titulo']:
        snapshot['assunto'] = snapshot['planner_titulo']

    return snapshot


def _snapshot_planner_recebido(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Retorna hash remoto somente quando o flow enviou o estado Planner completo."""
    if any(payload.get(campo) is None for campo in _CAMPOS_PLANNER):
        return None
    return {
        'planner_titulo': _texto(payload['planner_titulo']),
        'planner_status': _texto(payload['planner_status']),
        'planner_percentual': int(payload['planner_percentual']),
        'planner_prazo': _texto(payload['planner_prazo']),
    }


def _aplicar_snapshot(record: CopilotMemoryRecord, snapshot: dict[str, Any]) -> None:
    for campo in _CAMPOS_CONTEUDO:
        setattr(record, campo, snapshot[campo])


def _serializar(record: CopilotMemoryRecord, *, changed: bool | None = None) -> dict[str, Any]:
    resultado = {
        'memoryId': record.memory_id,
        'plannerTaskId': record.planner_task_id,
        'assunto': record.assunto,
        'contexto': record.contexto,
        'estadoAtual': record.estado_atual,
        'decisao': record.decisao,
        'pendencia': record.pendencia,
        'proximoPasso': record.proximo_passo,
        'fonteUrl': record.fonte_url,
        'dataFonte': record.data_fonte,
        'validade': record.validade,
        'plannerTitulo': record.planner_titulo,
        'plannerStatus': record.planner_status,
        'plannerPercentual': record.planner_percentual,
        'plannerPrazo': record.planner_prazo,
        'ultimaOrigem': record.ultima_origem,
        'contentHash': record.content_hash,
        'versao': record.versao,
        'correlationId': record.correlation_id,
        'atualizarPlanner': record.atualizar_planner,
        'plannerSyncStatus': record.planner_sync_status,
        'plannerAppliedHash': record.planner_applied_hash,
        'ultimoErro': record.ultimo_erro,
        'criadoEm': record.criado_em.isoformat() if record.criado_em else None,
        'atualizadoEm': record.atualizado_em.isoformat() if record.atualizado_em else None,
    }
    if changed is not None:
        resultado['changed'] = changed
    return resultado


def _registrar_historico(
    db: Session,
    record: CopilotMemoryRecord,
    snapshot: dict[str, Any],
    origem: str,
    correlation_id: str,
) -> None:
    db.add(CopilotMemoryHistory(
        memory_id=record.memory_id,
        versao=record.versao,
        content_hash=record.content_hash,
        origem=origem,
        correlation_id=correlation_id,
        snapshot_json=json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
    ))


def _localizar_record(
    db: Session,
    memory_id: str | None,
    planner_task_id: str | None,
) -> CopilotMemoryRecord | None:
    if memory_id:
        record = db.query(CopilotMemoryRecord).filter(CopilotMemoryRecord.memory_id == memory_id).first()
        if record:
            return record
    if planner_task_id:
        return db.query(CopilotMemoryRecord).filter(
            CopilotMemoryRecord.planner_task_id == planner_task_id
        ).first()
    return None


def sincronizar_item(db: Session, payload: dict[str, Any], correlation_id: str) -> dict[str, Any]:
    origem = _texto(payload.get('origem') or 'reqsys').lower()
    planner_task_id = _texto(payload.get('planner_task_id')) or None
    memory_id_recebido = _texto(payload.get('memory_id')) or None
    record = _localizar_record(db, memory_id_recebido, planner_task_id)

    memory_id = record.memory_id if record else (memory_id_recebido or _gerar_memory_id(planner_task_id or ''))
    if not memory_id:
        raise ValueError('memoryId ou plannerTaskId é obrigatório')

    # Um Planner ainda refletindo o estado antigo não pode apagar uma alteração
    # Excel -> Planner que está aguardando aplicação. Alteração remota diferente
    # do último estado confirmado vira conflito explícito e fail-closed.
    if record and origem == 'planner' and record.planner_sync_status == STATUS_PENDENTE:
        planner_recebido = _snapshot_planner_recebido(payload)
        if planner_recebido is None:
            raise ValueError('origem=planner exige estado completo: título, status, percentual e prazo')
        remoto_hash = _hash_json(planner_recebido)
        if remoto_hash == record.planner_applied_hash:
            record.ultima_origem = origem
            record.correlation_id = correlation_id
            db.add(record)
            db.commit()
            db.refresh(record)
            return _serializar(record, changed=False)

        record.planner_sync_status = STATUS_CONFLITO
        record.ultimo_erro = 'Planner alterado enquanto existia atualização local pendente; revisão necessária'
        record.ultima_origem = origem
        record.correlation_id = correlation_id
        db.add(record)
        db.commit()
        db.refresh(record)
        return _serializar(record, changed=False)

    snapshot = _montar_snapshot(payload, record)
    novo_content_hash = _content_hash(snapshot)
    novo_planner_hash = _planner_hash(snapshot)
    solicitar_planner = bool(payload.get('atualizar_planner'))

    if record and record.content_hash == novo_content_hash:
        record.ultima_origem = origem
        record.correlation_id = correlation_id

        if origem == 'planner':
            record.planner_applied_hash = novo_planner_hash
            record.atualizar_planner = False
            record.planner_sync_status = STATUS_SINCRONIZADO
            record.ultimo_erro = ''
        elif solicitar_planner:
            if not record.planner_task_id:
                raise ValueError('plannerTaskId é obrigatório para atualizar o Planner')
            if novo_planner_hash != record.planner_applied_hash:
                record.atualizar_planner = True
                record.planner_sync_status = STATUS_PENDENTE
                record.ultimo_erro = ''
            else:
                record.atualizar_planner = False
                record.planner_sync_status = STATUS_SINCRONIZADO
                record.ultimo_erro = ''

        db.add(record)
        db.commit()
        db.refresh(record)
        return _serializar(record, changed=False)

    if record is None:
        record = CopilotMemoryRecord(
            memory_id=memory_id,
            content_hash=novo_content_hash,
            versao=1,
            ultima_origem=origem,
            correlation_id=correlation_id,
        )
        _aplicar_snapshot(record, snapshot)
        db.add(record)
        db.flush()
    else:
        _aplicar_snapshot(record, snapshot)
        record.content_hash = novo_content_hash
        record.versao += 1
        record.ultima_origem = origem
        record.correlation_id = correlation_id

    if origem == 'planner':
        record.planner_applied_hash = novo_planner_hash
        record.atualizar_planner = False
        record.planner_sync_status = STATUS_SINCRONIZADO
        record.ultimo_erro = ''
    elif solicitar_planner:
        if not record.planner_task_id:
            raise ValueError('plannerTaskId é obrigatório para atualizar o Planner')
        if novo_planner_hash != record.planner_applied_hash:
            record.atualizar_planner = True
            record.planner_sync_status = STATUS_PENDENTE
            record.ultimo_erro = ''
        else:
            record.atualizar_planner = False
            record.planner_sync_status = STATUS_SINCRONIZADO
            record.ultimo_erro = ''
    elif not record.planner_sync_status:
        record.planner_sync_status = STATUS_NAO_SOLICITADO

    _registrar_historico(db, record, snapshot, origem, correlation_id)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _serializar(record, changed=True)


def sincronizar_lote(
    db: Session,
    items: list[dict[str, Any]],
    correlation_id: str,
) -> dict[str, Any]:
    resultados = [sincronizar_item(db, item, correlation_id) for item in items]
    return {
        'items': resultados,
        'total': len(resultados),
        'alterados': sum(1 for item in resultados if item.get('changed')),
        'inalterados': sum(1 for item in resultados if not item.get('changed')),
        'correlationId': correlation_id,
    }


def listar_memorias(
    db: Session,
    *,
    planner_task_id: str | None = None,
    validade: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    query = db.query(CopilotMemoryRecord)
    if planner_task_id:
        query = query.filter(CopilotMemoryRecord.planner_task_id == planner_task_id)
    if validade:
        query = query.filter(CopilotMemoryRecord.validade == validade)
    records = query.order_by(CopilotMemoryRecord.id.desc()).limit(limit).all()
    return [_serializar(record) for record in records]


def listar_comandos_planner(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    records = (
        db.query(CopilotMemoryRecord)
        .filter(CopilotMemoryRecord.atualizar_planner.is_(True))
        .filter(CopilotMemoryRecord.planner_sync_status == STATUS_PENDENTE)
        .filter(CopilotMemoryRecord.planner_task_id.is_not(None))
        .order_by(CopilotMemoryRecord.id.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            'memoryId': record.memory_id,
            'plannerTaskId': record.planner_task_id,
            'plannerTitulo': record.planner_titulo,
            'plannerStatus': record.planner_status,
            'plannerPercentual': record.planner_percentual,
            'plannerPrazo': record.planner_prazo,
            'desiredHash': _planner_hash(_base_snapshot(record)),
            'correlationId': record.correlation_id,
        }
        for record in records
    ]


def confirmar_comando_planner(
    db: Session,
    memory_id: str,
    *,
    sucesso: bool,
    correlation_id: str,
    planner_task_id: str | None = None,
    erro: str | None = None,
) -> dict[str, Any]:
    record = db.query(CopilotMemoryRecord).filter(CopilotMemoryRecord.memory_id == memory_id).first()
    if record is None:
        raise ValueError(f'Memória {memory_id} não encontrada')

    if planner_task_id:
        record.planner_task_id = _texto(planner_task_id)

    if sucesso:
        record.planner_applied_hash = _planner_hash(_base_snapshot(record))
        record.atualizar_planner = False
        record.planner_sync_status = STATUS_SINCRONIZADO
        record.ultimo_erro = ''
    else:
        record.atualizar_planner = True
        record.planner_sync_status = STATUS_ERRO
        record.ultimo_erro = _texto(erro)[:500] or 'Power Automate não confirmou atualização do Planner'

    record.ultima_origem = 'reqsys'
    record.correlation_id = correlation_id
    db.add(record)
    db.commit()
    db.refresh(record)
    return _serializar(record, changed=False)


def listar_historico(db: Session, memory_id: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = (
        db.query(CopilotMemoryHistory)
        .filter(CopilotMemoryHistory.memory_id == memory_id)
        .order_by(CopilotMemoryHistory.versao.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            'memoryId': row.memory_id,
            'versao': row.versao,
            'contentHash': row.content_hash,
            'origem': row.origem,
            'correlationId': row.correlation_id,
            'snapshot': json.loads(row.snapshot_json),
            'criadoEm': row.criado_em.isoformat() if row.criado_em else None,
        }
        for row in rows
    ]


def resumo_memoria(db: Session) -> dict[str, int]:
    total = db.query(CopilotMemoryRecord).count()
    pendentes = db.query(CopilotMemoryRecord).filter(
        CopilotMemoryRecord.planner_sync_status == STATUS_PENDENTE
    ).count()
    conflitos = db.query(CopilotMemoryRecord).filter(
        CopilotMemoryRecord.planner_sync_status == STATUS_CONFLITO
    ).count()
    erros = db.query(CopilotMemoryRecord).filter(
        CopilotMemoryRecord.planner_sync_status == STATUS_ERRO
    ).count()
    return {
        'total': total,
        'plannerPendentes': pendentes,
        'conflitos': conflitos,
        'erros': erros,
    }
