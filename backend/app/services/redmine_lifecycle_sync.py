"""Reconciliação governada ReqSys <-> Redmine para o lifecycle.

Incremento 1 da issue #1686:
- ReqSys -> Redmine: somente subject/description.
- Redmine -> ReqSys: snapshot de execução + journals em auditoria.
- estado/checkpoint persistido em ``VinculoGit`` para evitar migração neste incremento.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.auditoria import AuditoriaEvento
from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit
from app.services.redmine_api import (
    atualizar_issue_redmine,
    montar_campos_requisito_redmine,
    obter_issue_redmine,
)

SYNC_STATE_TYPE = 'redmine_sync_state'
SYNC_STATE_VERSION = 1
MAX_JOURNAL_NOTES_CHARS = 4000


class RedmineLifecycleSyncError(RuntimeError):
    pass


def _fingerprint(payload: Any) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        default=str,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _issue_link(db: Session, requisito: Requisito) -> VinculoGit:
    link = (
        db.query(VinculoGit)
        .filter(VinculoGit.requisito_id == requisito.id)
        .filter(VinculoGit.provedor == 'redmine')
        .filter(VinculoGit.tipo == 'issue')
        .order_by(VinculoGit.id.desc())
        .first()
    )
    if not link:
        raise RedmineLifecycleSyncError(
            f'Requisito {requisito.codigo} não possui vínculo de issue Redmine.'
        )
    try:
        issue_id = int(link.referencia)
    except (TypeError, ValueError) as exc:
        raise RedmineLifecycleSyncError(
            f'Vínculo Redmine inválido para {requisito.codigo}: {link.referencia!r}.'
        ) from exc
    if issue_id <= 0:
        raise RedmineLifecycleSyncError(
            f'Vínculo Redmine inválido para {requisito.codigo}: {link.referencia!r}.'
        )
    return link


def _sync_state_link(
    db: Session,
    requisito: Requisito,
    issue_id: int,
) -> VinculoGit | None:
    return (
        db.query(VinculoGit)
        .filter(VinculoGit.requisito_id == requisito.id)
        .filter(VinculoGit.provedor == 'redmine')
        .filter(VinculoGit.tipo == SYNC_STATE_TYPE)
        .filter(VinculoGit.referencia == str(issue_id))
        .order_by(VinculoGit.id.desc())
        .first()
    )


def _load_sync_state(link: VinculoGit | None) -> dict[str, Any]:
    if not link or not link.titulo:
        return {}
    try:
        value = json.loads(link.titulo)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _owned_remote_content(issue: dict[str, Any]) -> dict[str, str]:
    return {
        'subject': str(issue.get('subject') or ''),
        'description': str(issue.get('description') or ''),
    }


def _execution_snapshot(issue: dict[str, Any]) -> dict[str, Any]:
    status = issue.get('status') if isinstance(issue.get('status'), dict) else {}
    assigned = issue.get('assigned_to') if isinstance(issue.get('assigned_to'), dict) else {}
    return {
        'status_id': status.get('id'),
        'status_name': status.get('name'),
        'assignee_id': assigned.get('id'),
        'assignee_name': assigned.get('name'),
        'done_ratio': issue.get('done_ratio'),
    }


def _journal_id(journal: dict[str, Any]) -> int:
    try:
        return int(journal.get('id') or 0)
    except (TypeError, ValueError):
        return 0


def _new_journals(issue: dict[str, Any], last_journal_id: int) -> list[dict[str, Any]]:
    journals = issue.get('journals')
    if not isinstance(journals, list):
        return []
    return sorted(
        [
            journal
            for journal in journals
            if isinstance(journal, dict) and _journal_id(journal) > last_journal_id
        ],
        key=_journal_id,
    )


def _journal_event(
    *,
    requisito: Requisito,
    issue_id: int,
    journal: dict[str, Any],
    correlation_id: str,
    actor: str,
) -> AuditoriaEvento | None:
    notes = str(journal.get('notes') or '').strip()
    if not notes:
        return None

    user = journal.get('user') if isinstance(journal.get('user'), dict) else {}
    payload = {
        'direction': 'redmine_to_reqsys',
        'redmine_issue_id': issue_id,
        'journal_id': _journal_id(journal),
        'author_id': user.get('id'),
        'author_name': user.get('name'),
        'created_on': journal.get('created_on'),
        'notes': notes[:MAX_JOURNAL_NOTES_CHARS],
        'notes_truncated': len(notes) > MAX_JOURNAL_NOTES_CHARS,
        'notes_sha256': hashlib.sha256(notes.encode('utf-8')).hexdigest(),
    }
    return AuditoriaEvento(
        correlation_id=correlation_id,
        usuario=actor,
        acao='REDMINE_JOURNAL_IMPORTADO',
        entidade='requisito',
        entidade_id=str(requisito.id),
        payload_minimo=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def _audit_event(
    *,
    requisito: Requisito,
    correlation_id: str,
    actor: str,
    action: str,
    payload: dict[str, Any],
) -> AuditoriaEvento:
    return AuditoriaEvento(
        correlation_id=correlation_id,
        usuario=actor,
        acao=action,
        entidade='requisito',
        entidade_id=str(requisito.id),
        payload_minimo=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def sincronizar_requisito_redmine(
    db: Session,
    *,
    requisito: Requisito,
    correlation_id: str,
    actor: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    issue_link = _issue_link(db, requisito)
    issue_id = int(issue_link.referencia)
    state_link = _sync_state_link(db, requisito, issue_id)
    state_before = _load_sync_state(state_link)
    last_journal_id = int(state_before.get('last_journal_id') or 0)

    desired = montar_campos_requisito_redmine(requisito)
    reqsys_fingerprint = _fingerprint(desired)

    issue_before = obter_issue_redmine(issue_id, incluir_journals=True)
    remote_content_before = _owned_remote_content(issue_before)
    changed_fields = {
        key: value
        for key, value in desired.items()
        if remote_content_before.get(key) != value
    }

    issue_effective = issue_before
    applied_fields: dict[str, Any] = {}
    if changed_fields and not dry_run:
        applied_fields = atualizar_issue_redmine(issue_id, changed_fields)
        # Leitura independente obrigatória: HTTP 2xx não é aceito como prova de efeito.
        issue_effective = obter_issue_redmine(issue_id, incluir_journals=True)
        remote_content_after = _owned_remote_content(issue_effective)
        not_applied = {
            key: value
            for key, value in changed_fields.items()
            if remote_content_after.get(key) != value
        }
        if not_applied:
            raise RedmineLifecycleSyncError(
                'Redmine respondeu à atualização, mas a leitura independente não confirmou '
                f'os campos: {", ".join(sorted(not_applied))}.'
            )

    execution = _execution_snapshot(issue_effective)
    execution_fingerprint = _fingerprint(execution)
    execution_changed = state_before.get('execution_fingerprint') != execution_fingerprint

    journals = _new_journals(issue_effective, last_journal_id)
    max_journal_id = max([last_journal_id] + [_journal_id(journal) for journal in journals])
    journal_events = [
        event
        for event in (
            _journal_event(
                requisito=requisito,
                issue_id=issue_id,
                journal=journal,
                correlation_id=correlation_id,
                actor=actor,
            )
            for journal in journals
        )
        if event is not None
    ]

    state_after = {
        'version': SYNC_STATE_VERSION,
        'reqsys_fingerprint': reqsys_fingerprint,
        'execution_fingerprint': execution_fingerprint,
        'last_journal_id': max_journal_id,
        'execution': execution,
    }
    state_changed = state_after != state_before

    if not dry_run:
        if applied_fields:
            db.add(
                _audit_event(
                    requisito=requisito,
                    correlation_id=correlation_id,
                    actor=actor,
                    action='REDMINE_SYNC_REQSYS_TO_REDMINE',
                    payload={
                        'direction': 'reqsys_to_redmine',
                        'redmine_issue_id': issue_id,
                        'changed_fields': sorted(applied_fields),
                        'reqsys_fingerprint': reqsys_fingerprint,
                        'remote_before_fingerprint': _fingerprint(remote_content_before),
                        'remote_after_fingerprint': _fingerprint(_owned_remote_content(issue_effective)),
                    },
                )
            )

        if execution_changed:
            db.add(
                _audit_event(
                    requisito=requisito,
                    correlation_id=correlation_id,
                    actor=actor,
                    action='REDMINE_SYNC_REDMINE_TO_REQSYS',
                    payload={
                        'direction': 'redmine_to_reqsys',
                        'redmine_issue_id': issue_id,
                        'changed_fields': [
                            key
                            for key, value in execution.items()
                            if (state_before.get('execution') or {}).get(key) != value
                        ],
                        'execution': execution,
                        'execution_fingerprint': execution_fingerprint,
                    },
                )
            )

        for event in journal_events:
            db.add(event)

        if state_changed:
            serialized = json.dumps(state_after, ensure_ascii=False, sort_keys=True)
            if state_link is None:
                state_link = VinculoGit(
                    requisito_codigo=requisito.codigo,
                    requisito_id=requisito.id,
                    tipo=SYNC_STATE_TYPE,
                    provedor='redmine',
                    repo='redmine',
                    referencia=str(issue_id),
                    url=issue_link.url,
                    titulo=serialized,
                    autor=actor,
                )
            else:
                state_link.titulo = serialized
                state_link.url = issue_link.url
                state_link.autor = actor
            db.add(state_link)

        if applied_fields or execution_changed or journal_events or state_changed:
            db.commit()

    return {
        'requisito_id': requisito.id,
        'codigo': requisito.codigo,
        'redmine_issue_id': issue_id,
        'dry_run': dry_run,
        'reqsys_to_redmine': {
            'planned': bool(changed_fields),
            'applied': bool(applied_fields),
            'changed_fields': sorted(changed_fields),
            'fingerprint': reqsys_fingerprint,
        },
        'redmine_to_reqsys': {
            'execution_changed': execution_changed,
            'execution': execution,
            'execution_fingerprint': execution_fingerprint,
            'new_journal_ids': [_journal_id(journal) for journal in journals],
            'imported_comment_count': len(journal_events),
            'last_journal_id': max_journal_id,
        },
        'state_changed': state_changed,
        'mutation_count': (
            (1 if applied_fields else 0)
            + (1 if execution_changed else 0)
            + len(journal_events)
            + (1 if state_changed else 0)
        )
        if not dry_run
        else 0,
    }
