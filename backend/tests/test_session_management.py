from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.security_session_state import SecuritySessionState
from app.services import session_management as svc


def _session():
    engine = create_engine('sqlite:///:memory:')
    SecuritySessionState.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return factory(), engine


def test_snapshot_inicializa_epoch_zero_sem_expor_segredo():
    db, engine = _session()
    try:
        state = svc.snapshot(db)
        assert state.session_epoch == 0
        assert state.authz_version.startswith('rbac-')
        assert state.invalidated_at is None
        assert 'secret' not in str(state.__dict__).lower()
        assert 'token' not in str(state.__dict__).lower()
    finally:
        db.close()
        engine.dispose()


def test_invalidate_all_incrementa_epoch_e_persiste_evidencia_sanitizada():
    db, engine = _session()
    try:
        first = svc.invalidate_all(
            actor='ad***@example.com',
            reason='Alteração controlada de RBAC',
            correlation_id='corr-session-test-1',
            db=db,
        )
        second = svc.invalidate_all(
            actor='ad***@example.com',
            reason='Segundo reset controlado',
            correlation_id='corr-session-test-2',
            db=db,
        )

        assert first.session_epoch == 1
        assert second.session_epoch == 2
        assert second.invalidated_by == 'ad***@example.com'
        assert second.correlation_id == 'corr-session-test-2'
        assert second.invalidated_at is not None
    finally:
        db.close()
        engine.dispose()


def test_validate_token_security_bloqueia_epoch_antigo(monkeypatch):
    fake = svc.SessionSecuritySnapshot(
        session_epoch=3,
        authz_version='rbac-atual',
        invalidated_at=datetime.now(UTC),
        invalidated_by='admin',
        invalidation_reason='teste',
        correlation_id='corr',
    )
    monkeypatch.setattr(svc, 'snapshot', lambda db=None: fake)

    valid, reason = svc.validate_token_security({'session_epoch': 2, 'authz_version': 'rbac-atual'})
    assert valid is False
    assert reason == 'SESSION_REVOKED'


def test_validate_token_security_bloqueia_authz_desatualizada(monkeypatch):
    fake = svc.SessionSecuritySnapshot(
        session_epoch=4,
        authz_version='rbac-nova',
        invalidated_at=None,
        invalidated_by=None,
        invalidation_reason=None,
        correlation_id=None,
    )
    monkeypatch.setattr(svc, 'snapshot', lambda db=None: fake)

    valid, reason = svc.validate_token_security({'session_epoch': 4, 'authz_version': 'rbac-antiga'})
    assert valid is False
    assert reason == 'AUTHORIZATION_CHANGED'


def test_token_legado_so_e_aceito_antes_do_primeiro_reset(monkeypatch):
    before = svc.SessionSecuritySnapshot(0, 'rbac-atual', None, None, None, None)
    monkeypatch.setattr(svc, 'snapshot', lambda db=None: before)
    assert svc.validate_token_security({}) == (True, None)

    after = svc.SessionSecuritySnapshot(1, 'rbac-atual', None, None, None, None)
    monkeypatch.setattr(svc, 'snapshot', lambda db=None: after)
    assert svc.validate_token_security({}) == (False, 'SESSION_REVOKED')
