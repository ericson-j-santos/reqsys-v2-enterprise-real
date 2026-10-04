from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.gestao_ti import RequisitoServico, ServicoTI

logger = logging.getLogger('reqsys.gestao_ti.seed')

REQSYS_SERVICO_ID = 'bde5fd56-5b4f-4ee4-8d64-5aa5f755e3ef'
REQSYS_CODIGO = 'REQSYS'

_ATRIBUTOS_CANONICOS = {
    'nome': 'ReqSys',
    'descricao': 'Plataforma corporativa de requisitos e gestão orientada a dados.',
    'criticidade': 'alta',
    'responsavel_tecnico': 'Equipe ReqSys',
    'responsavel_negocio': 'Gestão de Produtos',
    'versao_catalogo': 1,
    'ativo': True,
}


@dataclass(frozen=True)
class ResultadoSeedGestaoTI:
    acao: str
    servico_id: str
    vinculos_migrados: int = 0


def _atualizar_atributos_canonicos(servico: ServicoTI) -> None:
    servico.codigo = REQSYS_CODIGO
    for campo, valor in _ATRIBUTOS_CANONICOS.items():
        setattr(servico, campo, valor)


def reconciliar_servico_reqsys(db: Session) -> ResultadoSeedGestaoTI:
    """Garante a mesma identidade do ReqSys em todos os bancos e ambientes."""
    canonico = db.get(ServicoTI, REQSYS_SERVICO_ID)
    por_codigo = db.query(ServicoTI).filter(ServicoTI.codigo == REQSYS_CODIGO).one_or_none()

    if canonico is not None and por_codigo is not None and canonico is not por_codigo:
        raise RuntimeError('Conflito de identidade: UUID e código REQSYS pertencem a serviços distintos.')

    if canonico is not None:
        _atualizar_atributos_canonicos(canonico)
        db.commit()
        logger.info('gestao_ti_seed_reconciliado acao=atualizado servico_id=%s', REQSYS_SERVICO_ID)
        return ResultadoSeedGestaoTI('atualizado', REQSYS_SERVICO_ID)

    if por_codigo is None:
        servico = ServicoTI(servico_id=REQSYS_SERVICO_ID, codigo=REQSYS_CODIGO, **_ATRIBUTOS_CANONICOS)
        db.add(servico)
        db.commit()
        logger.info('gestao_ti_seed_reconciliado acao=criado servico_id=%s', REQSYS_SERVICO_ID)
        return ResultadoSeedGestaoTI('criado', REQSYS_SERVICO_ID)

    id_legado = por_codigo.servico_id
    por_codigo.codigo = f'REQSYS_LEGADO_{id_legado[:8].upper()}'
    db.flush()

    canonico = ServicoTI(servico_id=REQSYS_SERVICO_ID, codigo=REQSYS_CODIGO, **_ATRIBUTOS_CANONICOS)
    db.add(canonico)
    db.flush()

    vinculos_migrados = (
        db.query(RequisitoServico)
        .filter(RequisitoServico.servico_id == id_legado)
        .update({RequisitoServico.servico_id: REQSYS_SERVICO_ID}, synchronize_session=False)
    )
    db.delete(por_codigo)
    db.commit()
    logger.info(
        'gestao_ti_seed_reconciliado acao=migrado servico_id_legado=%s servico_id=%s vinculos_migrados=%s',
        id_legado,
        REQSYS_SERVICO_ID,
        vinculos_migrados,
    )
    return ResultadoSeedGestaoTI('migrado', REQSYS_SERVICO_ID, vinculos_migrados)


def reconciliar_servico_reqsys_no_startup(session_factory) -> ResultadoSeedGestaoTI | None:
    db = session_factory()
    try:
        return reconciliar_servico_reqsys(db)
    except Exception:
        db.rollback()
        logger.exception('gestao_ti_seed_reconciliacao_falhou')
        return None
    finally:
        db.close()
