"""Reconciliação em lote governada ReqSys <-> Redmine.

Incremento 2 da issue #1686, sobre o reconciliador por requisito do Incremento 1
(``redmine_lifecycle_sync``):

- reserva/lock por requisito para impedir dois workers simultâneos;
- backoff exponencial e limite de tentativas;
- quarentena (DLQ) de conflitos permanentes, liberável por operação explícita;
- lote com resultado por item e agregados.

O estado de controle vive em uma linha própria de ``VinculoGit``
(``tipo='redmine_sync_control'``), separada do checkpoint do Incremento 1
(``tipo='redmine_sync_state'``), para que nenhuma das duas escritas sobrescreva
a outra e para não exigir migração neste incremento.

O lock é adquirido por compare-and-swap no próprio ``UPDATE`` (cláusula
``WHERE titulo = <valor lido>``): se outra sessão avançou o estado, o
``rowcount`` volta zero e o requisito é pulado em vez de processado duas vezes.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.auditoria import AuditoriaEvento
from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit
from app.services.github_redmine import IntegracaoError
from app.services.redmine_lifecycle_sync import (
    RedmineLifecycleSyncError,
    sincronizar_requisito_redmine,
)

CONTROL_TYPE = 'redmine_sync_control'
CONTROL_VERSION = 1
ISSUE_LINK_TYPE = 'issue'
PROVIDER = 'redmine'

DEFAULT_LOTE_MAX = 10
DEFAULT_LOCK_TIMEOUT_MINUTOS = 10
DEFAULT_MAX_TENTATIVAS = 5
DEFAULT_BACKOFF_BASE_MINUTOS = 5
DEFAULT_BACKOFF_MAX_MINUTOS = 240

MAX_ERROR_CHARS = 500

OUTCOME_SYNCED = 'sincronizado'
OUTCOME_SKIPPED_LOCK = 'pulado_lock'
OUTCOME_SKIPPED_BACKOFF = 'pulado_backoff'
OUTCOME_SKIPPED_QUARANTINE = 'pulado_quarentena'
OUTCOME_QUARANTINED = 'quarentenado'
OUTCOME_FAILED = 'falhou'
OUTCOME_DRY_RUN = 'dry_run'


class RedmineLifecycleBatchError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _dump(control: dict[str, Any]) -> str:
    return json.dumps(control, ensure_ascii=False, sort_keys=True)


def _load(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _empty_control() -> dict[str, Any]:
    return {
        'version': CONTROL_VERSION,
        'lock': None,
        'attempts': 0,
        'last_error': None,
        'last_error_at': None,
        'next_attempt_at': None,
        'quarantined': False,
        'quarantine_reason': None,
        'quarantined_at': None,
        'last_success_at': None,
        'last_correlation_id': None,
    }


def _issue_link(db: Session, requisito: Requisito) -> VinculoGit | None:
    return (
        db.query(VinculoGit)
        .filter(VinculoGit.requisito_id == requisito.id)
        .filter(VinculoGit.provedor == PROVIDER)
        .filter(VinculoGit.tipo == ISSUE_LINK_TYPE)
        .order_by(VinculoGit.id.desc())
        .first()
    )


def _control_links(db: Session, requisito: Requisito, issue_id: int) -> list[VinculoGit]:
    return (
        db.query(VinculoGit)
        .filter(VinculoGit.requisito_id == requisito.id)
        .filter(VinculoGit.provedor == PROVIDER)
        .filter(VinculoGit.tipo == CONTROL_TYPE)
        .filter(VinculoGit.referencia == str(issue_id))
        .order_by(VinculoGit.id.asc())
        .all()
    )


def _ensure_control_link(
    db: Session,
    requisito: Requisito,
    *,
    issue_id: int,
    issue_url: str | None,
    actor: str,
) -> VinculoGit:
    """Devolve a linha canônica de controle, tolerando criação concorrente.

    Sem constraint única disponível neste incremento, duas sessões podem criar a
    linha ao mesmo tempo. A canônica é sempre o menor ``id``; uma duplicata
    criada por esta sessão é removida em seguida, de modo que o lock passa a
    disputar uma única linha.
    """
    existing = _control_links(db, requisito, issue_id)
    if existing:
        return existing[0]

    criado = VinculoGit(
        requisito_codigo=requisito.codigo,
        requisito_id=requisito.id,
        tipo=CONTROL_TYPE,
        provedor=PROVIDER,
        repo=PROVIDER,
        referencia=str(issue_id),
        url=issue_url,
        titulo=_dump(_empty_control()),
        autor=actor,
    )
    db.add(criado)
    db.commit()

    links = _control_links(db, requisito, issue_id)
    canonical = links[0]
    if canonical.id != criado.id:
        db.delete(criado)
        db.commit()
    return canonical


def _audit(
    db: Session,
    *,
    requisito: Requisito,
    correlation_id: str,
    actor: str,
    action: str,
    payload: dict[str, Any],
) -> None:
    db.add(
        AuditoriaEvento(
            correlation_id=correlation_id,
            usuario=actor,
            acao=action,
            entidade='requisito',
            entidade_id=str(requisito.id),
            payload_minimo=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        )
    )
    db.commit()


def _swap_control(db: Session, link: VinculoGit, raw_before: str | None, control: dict[str, Any]) -> bool:
    """Grava o controle somente se ninguém mais o alterou (compare-and-swap)."""
    serialized = _dump(control)
    updated = (
        db.query(VinculoGit)
        .filter(VinculoGit.id == link.id)
        .filter(VinculoGit.titulo == raw_before)
        .update({'titulo': serialized}, synchronize_session=False)
    )
    db.commit()
    if updated != 1:
        db.refresh(link)
        return False
    db.refresh(link)
    return True


def _acquire_lock(
    db: Session,
    link: VinculoGit,
    *,
    owner: str,
    correlation_id: str,
    lock_timeout_minutos: int,
    agora: datetime,
) -> tuple[bool, dict[str, Any]]:
    raw_before = link.titulo
    control = {**_empty_control(), **_load(raw_before)}

    lock = control.get('lock') if isinstance(control.get('lock'), dict) else None
    if lock:
        expires_at = _parse(lock.get('expires_at'))
        if expires_at and expires_at > agora:
            return False, control

    control['lock'] = {
        'owner': owner,
        'correlation_id': correlation_id,
        'acquired_at': _iso(agora),
        'expires_at': _iso(agora + timedelta(minutes=max(1, lock_timeout_minutos))),
    }
    if not _swap_control(db, link, raw_before, control):
        return False, {**_empty_control(), **_load(link.titulo)}
    return True, control


def _release_lock(db: Session, link: VinculoGit, control: dict[str, Any]) -> None:
    """Libera a reserva gravando o controle sem lock.

    Se o compare-and-swap falhar, outra sessão já avançou o estado (por exemplo,
    um lock expirado assumido por outro worker) e nada é sobrescrito. Nenhum
    chamador precisa do estado resultante: quem decide segue com os valores
    locais da própria execução, e a leitura seguinte vem do banco.
    """
    raw_before = link.titulo
    _swap_control(db, link, raw_before, {**control, 'lock': None})


def _backoff_minutos(attempts: int, *, base_minutos: int, max_minutos: int) -> int:
    expoente = max(0, attempts - 1)
    bruto = max(1, base_minutos) * (2 ** min(expoente, 16))
    return int(min(bruto, max(1, max_minutos)))


def requisitos_com_vinculo_redmine(
    db: Session,
    *,
    requisito_ids: list[int] | None = None,
    limite: int | None = None,
) -> list[Requisito]:
    query = (
        db.query(Requisito)
        .join(VinculoGit, VinculoGit.requisito_id == Requisito.id)
        .filter(VinculoGit.provedor == PROVIDER)
        .filter(VinculoGit.tipo == ISSUE_LINK_TYPE)
    )
    if requisito_ids:
        query = query.filter(Requisito.id.in_(requisito_ids))
    query = query.order_by(Requisito.id.asc())
    requisitos: list[Requisito] = []
    vistos: set[int] = set()
    for requisito in query.all():
        if requisito.id in vistos:
            continue
        vistos.add(requisito.id)
        requisitos.append(requisito)
        if limite is not None and len(requisitos) >= limite:
            break
    return requisitos


def reconciliar_requisito(
    db: Session,
    *,
    requisito: Requisito,
    correlation_id: str,
    actor: str,
    worker_id: str | None = None,
    dry_run: bool = False,
    incluir_quarentena: bool = False,
    lock_timeout_minutos: int = DEFAULT_LOCK_TIMEOUT_MINUTOS,
    max_tentativas: int = DEFAULT_MAX_TENTATIVAS,
    backoff_base_minutos: int = DEFAULT_BACKOFF_BASE_MINUTOS,
    backoff_max_minutos: int = DEFAULT_BACKOFF_MAX_MINUTOS,
    agora: datetime | None = None,
) -> dict[str, Any]:
    """Reconcilia um requisito respeitando lock, backoff e quarentena."""
    agora = agora or _now()
    worker_id = worker_id or f'worker-{uuid4().hex[:12]}'

    issue_link = _issue_link(db, requisito)
    if issue_link is None:
        return {
            'requisito_id': requisito.id,
            'codigo': requisito.codigo,
            'outcome': OUTCOME_FAILED,
            'error_type': 'vinculo_ausente',
            'error_ref': correlation_id,
            'attempts': 0,
            'quarantined': False,
        }

    try:
        issue_id = int(issue_link.referencia)
    except (TypeError, ValueError):
        issue_id = 0
    if issue_id <= 0:
        return {
            'requisito_id': requisito.id,
            'codigo': requisito.codigo,
            'outcome': OUTCOME_FAILED,
            'error_type': 'vinculo_invalido',
            'error_ref': correlation_id,
            'attempts': 0,
            'quarantined': False,
        }

    if dry_run:
        # Dry-run não cria estado de controle nem adquire lock: apenas informa o
        # que SERIA processado, em formato deliberadamente distinto do real.
        links = _control_links(db, requisito, issue_id)
        control = {**_empty_control(), **_load(links[0].titulo if links else None)}
        next_attempt_at = _parse(control.get('next_attempt_at'))
        elegivel = not control.get('quarantined') and not (next_attempt_at and next_attempt_at > agora)
        return {
            'requisito_id': requisito.id,
            'codigo': requisito.codigo,
            'redmine_issue_id': issue_id,
            'outcome': OUTCOME_DRY_RUN,
            'would_process': bool(elegivel),
            'attempts': int(control.get('attempts') or 0),
            'quarantined': bool(control.get('quarantined')),
            'next_attempt_at': control.get('next_attempt_at'),
            'mutation_count': 0,
        }

    control_link = _ensure_control_link(
        db,
        requisito,
        issue_id=issue_id,
        issue_url=issue_link.url,
        actor=actor,
    )
    control = {**_empty_control(), **_load(control_link.titulo)}

    if control.get('quarantined') and not incluir_quarentena:
        return {
            'requisito_id': requisito.id,
            'codigo': requisito.codigo,
            'redmine_issue_id': issue_id,
            'outcome': OUTCOME_SKIPPED_QUARANTINE,
            'attempts': int(control.get('attempts') or 0),
            'quarantined': True,
            'quarantine_reason': control.get('quarantine_reason'),
        }

    next_attempt_at = _parse(control.get('next_attempt_at'))
    if next_attempt_at and next_attempt_at > agora:
        return {
            'requisito_id': requisito.id,
            'codigo': requisito.codigo,
            'redmine_issue_id': issue_id,
            'outcome': OUTCOME_SKIPPED_BACKOFF,
            'attempts': int(control.get('attempts') or 0),
            'quarantined': False,
            'next_attempt_at': control.get('next_attempt_at'),
        }

    acquired, control = _acquire_lock(
        db,
        control_link,
        owner=worker_id,
        correlation_id=correlation_id,
        lock_timeout_minutos=lock_timeout_minutos,
        agora=agora,
    )
    if not acquired:
        return {
            'requisito_id': requisito.id,
            'codigo': requisito.codigo,
            'redmine_issue_id': issue_id,
            'outcome': OUTCOME_SKIPPED_LOCK,
            'attempts': int(control.get('attempts') or 0),
            'quarantined': bool(control.get('quarantined')),
            'lock_owner': (control.get('lock') or {}).get('owner'),
        }

    try:
        resultado = sincronizar_requisito_redmine(
            db,
            requisito=requisito,
            correlation_id=correlation_id,
            actor=actor,
            dry_run=False,
        )
    except (RedmineLifecycleSyncError, IntegracaoError) as exc:
        attempts = int(control.get('attempts') or 0) + 1
        erro = str(exc)[:MAX_ERROR_CHARS]
        control['attempts'] = attempts
        control['last_error'] = erro
        control['last_error_at'] = _iso(agora)
        control['last_correlation_id'] = correlation_id

        quarentenado = attempts >= max(1, max_tentativas)
        if quarentenado:
            control['quarantined'] = True
            control['quarantine_reason'] = erro
            control['quarantined_at'] = _iso(agora)
            proximo_em = None
            next_attempt_at = None
        else:
            proximo_em = _backoff_minutos(
                attempts,
                base_minutos=backoff_base_minutos,
                max_minutos=backoff_max_minutos,
            )
            next_attempt_at = _iso(agora + timedelta(minutes=proximo_em))
        control['next_attempt_at'] = next_attempt_at

        _release_lock(db, control_link, control)
        _audit(
            db,
            requisito=requisito,
            correlation_id=correlation_id,
            actor=actor,
            action='REDMINE_SYNC_QUARENTENA' if quarentenado else 'REDMINE_SYNC_FALHA',
            payload={
                'redmine_issue_id': issue_id,
                'attempts': attempts,
                'max_tentativas': max_tentativas,
                'error': erro,
                'quarantined': quarentenado,
                'next_attempt_at': next_attempt_at,
                'backoff_minutos': proximo_em,
            },
        )
        return {
            'requisito_id': requisito.id,
            'codigo': requisito.codigo,
            'redmine_issue_id': issue_id,
            'outcome': OUTCOME_QUARANTINED if quarentenado else OUTCOME_FAILED,
            # O texto da falha fica no estado de controle e no evento de
            # auditoria; a resposta da API devolve apenas o tipo e a chave de
            # correlação, para não expor detalhe de exceção ao chamador.
            'error_type': type(exc).__name__,
            'error_ref': correlation_id,
            'attempts': attempts,
            'quarantined': quarentenado,
            'next_attempt_at': next_attempt_at,
            'backoff_minutos': proximo_em,
        }

    control['attempts'] = 0
    control['last_error'] = None
    control['last_error_at'] = None
    control['next_attempt_at'] = None
    control['last_success_at'] = _iso(agora)
    control['last_correlation_id'] = correlation_id
    _release_lock(db, control_link, control)

    return {
        'requisito_id': requisito.id,
        'codigo': requisito.codigo,
        'redmine_issue_id': issue_id,
        'outcome': OUTCOME_SYNCED,
        'attempts': 0,
        'quarantined': False,
        'mutation_count': resultado.get('mutation_count', 0),
        'sync': resultado,
    }


def reconciliar_lote(
    db: Session,
    *,
    correlation_id: str,
    actor: str,
    lote_max: int = DEFAULT_LOTE_MAX,
    dry_run: bool = False,
    requisito_ids: list[int] | None = None,
    incluir_quarentena: bool = False,
    lock_timeout_minutos: int = DEFAULT_LOCK_TIMEOUT_MINUTOS,
    max_tentativas: int = DEFAULT_MAX_TENTATIVAS,
    backoff_base_minutos: int = DEFAULT_BACKOFF_BASE_MINUTOS,
    backoff_max_minutos: int = DEFAULT_BACKOFF_MAX_MINUTOS,
    agora: datetime | None = None,
) -> dict[str, Any]:
    """Reconcilia um lote limitado de requisitos com vínculo Redmine."""
    agora = agora or _now()
    limite = max(1, int(lote_max or DEFAULT_LOTE_MAX))

    requisitos = requisitos_com_vinculo_redmine(
        db,
        requisito_ids=requisito_ids,
        limite=limite,
    )

    itens: list[dict[str, Any]] = []
    for requisito in requisitos:
        itens.append(
            reconciliar_requisito(
                db,
                requisito=requisito,
                correlation_id=f'{correlation_id}:{requisito.codigo}',
                actor=actor,
                dry_run=dry_run,
                incluir_quarentena=incluir_quarentena,
                lock_timeout_minutos=lock_timeout_minutos,
                max_tentativas=max_tentativas,
                backoff_base_minutos=backoff_base_minutos,
                backoff_max_minutos=backoff_max_minutos,
                agora=agora,
            )
        )

    contagens: dict[str, int] = {}
    for item in itens:
        outcome = str(item.get('outcome'))
        contagens[outcome] = contagens.get(outcome, 0) + 1

    return {
        'dry_run': dry_run,
        'correlation_id': correlation_id,
        'lote_max': limite,
        'avaliados': len(itens),
        'contagens': contagens,
        'mutation_count': sum(int(item.get('mutation_count') or 0) for item in itens),
        'itens': itens,
    }


def liberar_quarentena(
    db: Session,
    *,
    requisito: Requisito,
    correlation_id: str,
    actor: str,
    agora: datetime | None = None,
) -> dict[str, Any]:
    """Libera a quarentena de um requisito após tratamento humano do conflito."""
    agora = agora or _now()
    issue_link = _issue_link(db, requisito)
    if issue_link is None:
        raise RedmineLifecycleBatchError(
            f'Requisito {requisito.codigo} não possui vínculo de issue Redmine.'
        )
    try:
        issue_id = int(issue_link.referencia)
    except (TypeError, ValueError) as exc:
        raise RedmineLifecycleBatchError(
            f'Vínculo Redmine inválido para {requisito.codigo}: {issue_link.referencia!r}.'
        ) from exc

    links = _control_links(db, requisito, issue_id)
    if not links:
        return {
            'requisito_id': requisito.id,
            'codigo': requisito.codigo,
            'redmine_issue_id': issue_id,
            'released': False,
            'reason': 'sem_estado_de_controle',
        }

    control_link = links[0]
    raw_before = control_link.titulo
    control = {**_empty_control(), **_load(raw_before)}
    if not control.get('quarantined'):
        return {
            'requisito_id': requisito.id,
            'codigo': requisito.codigo,
            'redmine_issue_id': issue_id,
            'released': False,
            'reason': 'nao_estava_em_quarentena',
        }

    motivo_anterior = control.get('quarantine_reason')
    control['quarantined'] = False
    control['quarantine_reason'] = None
    control['quarantined_at'] = None
    control['attempts'] = 0
    control['next_attempt_at'] = None
    control['last_correlation_id'] = correlation_id

    if not _swap_control(db, control_link, raw_before, control):
        raise RedmineLifecycleBatchError(
            f'Estado de controle de {requisito.codigo} mudou durante a liberação; reexecute.'
        )

    _audit(
        db,
        requisito=requisito,
        correlation_id=correlation_id,
        actor=actor,
        action='REDMINE_SYNC_QUARENTENA_LIBERADA',
        payload={
            'redmine_issue_id': issue_id,
            'quarantine_reason_anterior': motivo_anterior,
            'liberado_em': _iso(agora),
        },
    )

    return {
        'requisito_id': requisito.id,
        'codigo': requisito.codigo,
        'redmine_issue_id': issue_id,
        'released': True,
        'quarantine_reason_anterior': motivo_anterior,
    }
