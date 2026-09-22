"""Retenção/purge de dados operacionais (ADR-043).

Padrao ouro de minimizacao de dados (ADR-002/LGPD): auditoria_eventos cresce
indefinidamente sem isso. A purga em si e registrada como evento de auditoria
(ADR-003) antes de ser aplicada, preservando rastreabilidade de que a retencao
foi executada mesmo apos os registros antigos serem removidos.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.secrets import get_secret
from app.core.telemetry import log_evento
from app.models.auditoria import AuditoriaEvento
from app.services.auditoria import registrar_evento

DEFAULT_AUDITORIA_RETENTION_DAYS = 180


def _retention_days() -> int:
    valor = get_secret('AUDITORIA_RETENTION_DAYS', str(DEFAULT_AUDITORIA_RETENTION_DAYS))
    try:
        return int(valor)
    except (TypeError, ValueError):
        return DEFAULT_AUDITORIA_RETENTION_DAYS


def purgar_auditoria_eventos(
    db: Session,
    retention_days: int | None = None,
    correlation_id: str = 'sistema-retencao',
) -> dict:
    """Remove auditoria_eventos mais antigos que `retention_days` e registra a purga."""
    dias = retention_days if retention_days is not None else _retention_days()
    cutoff = datetime.now(timezone.utc) - timedelta(days=dias)

    total = db.query(AuditoriaEvento).filter(AuditoriaEvento.criado_em < cutoff).count()

    if total:
        registrar_evento(
            db,
            correlation_id=correlation_id,
            usuario='sistema',
            acao='AUDITORIA_PURGE_EXECUTADO',
            entidade='auditoria_eventos',
            entidade_id='retention_job',
            payload_minimo=f'{{"retention_days": {dias}, "registros_removidos": {total}}}',
        )
        db.query(AuditoriaEvento).filter(AuditoriaEvento.criado_em < cutoff).delete(synchronize_session=False)
        db.commit()

    log_evento('auditoria_eventos.purge_executado', retention_days=dias, registros_removidos=total)

    return {'retention_days': dias, 'registros_removidos': total, 'cutoff': cutoff.isoformat()}
