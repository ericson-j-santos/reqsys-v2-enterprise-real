from datetime import UTC, datetime
from decimal import Decimal

from app.api import financeiro
from app.core.security import require_admin
from app.db import Base
from app.db import get_db
from app.main import app
from app.models.auditoria import AuditoriaEvento
from app.models.cdi_rate import CdiRate
from app.services.cdi_provider import CdiProviderError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _sqlite_file_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cdi-api.db'}", connect_args={'check_same_thread': False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    return session, engine


def test_cdi_latest_retorna_cache_interno(client, tmp_path):
    db_session, engine = _sqlite_file_session(tmp_path)
    rate = CdiRate(
        reference_date=datetime(2026, 7, 2).date(),
        daily_rate_percent=Decimal('0.052531'),
        daily_rate_decimal=Decimal('0.00052531'),
        source='bcb_sgs_12',
        source_url='https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json',
        raw_payload='{}',
        fetched_at=datetime.now(UTC),
    )
    db_session.add(rate)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get('/v1/financeiro/cdi/latest')
    finally:
        app.dependency_overrides.pop(get_db, None)
        db_session.close()
        engine.dispose()

    assert response.status_code == 200
    data = response.json()['data']
    assert data['reference_date'] == '2026-07-02'
    assert data['daily_rate_percent'] == 0.052531
    assert data['stale'] is False


def test_cdi_latest_404_quando_cache_vazio(client, tmp_path):
    db_session, engine = _sqlite_file_session(tmp_path)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get('/v1/financeiro/cdi/latest')
    finally:
        app.dependency_overrides.pop(get_db, None)
        db_session.close()
        engine.dispose()

    assert response.status_code == 404
    assert 'ainda nao foi carregada' in response.json()['detail']


def test_cdi_refresh_retorna_cache_com_warning_quando_bcb_falha(client, tmp_path, monkeypatch):
    db_session, engine = _sqlite_file_session(tmp_path)
    rate = CdiRate(
        reference_date=datetime(2026, 7, 2).date(),
        daily_rate_percent=Decimal('0.052531'),
        daily_rate_decimal=Decimal('0.00052531'),
        source='bcb_sgs_12',
        source_url='https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json',
        raw_payload='{}',
        fetched_at=datetime.now(UTC),
    )
    db_session.add(rate)
    db_session.commit()

    def override_get_db():
        yield db_session

    def fake_admin():
        return {'papel': 'admin'}

    def fake_refresh(db):
        raise CdiProviderError('BCB indisponivel')

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = fake_admin
    monkeypatch.setattr(financeiro, 'atualizar_cdi_do_bcb', fake_refresh)
    try:
        response = client.post('/v1/financeiro/cdi/refresh')
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_admin, None)
        db_session.close()
        engine.dispose()

    assert response.status_code == 200
    body = response.json()
    assert body['data']['stale'] is True
    assert 'Falha ao atualizar CDI' in body['meta']['warning']

    eventos = db_session.query(AuditoriaEvento).all()
    assert len(eventos) == 1
    assert eventos[0].acao == 'CDI_REFRESH_FALHA'
    assert eventos[0].entidade == 'cdi_rate'


def test_cdi_refresh_registra_auditoria_com_usuario_quando_sucesso(client, tmp_path, monkeypatch):
    db_session, engine = _sqlite_file_session(tmp_path)

    def override_get_db():
        yield db_session

    def fake_admin():
        return {'papel': 'admin', 'sub': 'analista@empresa.com'}

    def fake_refresh(db):
        return {
            'reference_date': '2026-07-03',
            'daily_rate_percent': 0.05,
            'daily_rate_decimal': 0.0005,
            'source': 'bcb_sgs_12',
            'source_url': 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json',
            'fetched_at': datetime.now(UTC).isoformat(),
            'stale': False,
        }

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = fake_admin
    monkeypatch.setattr(financeiro, 'atualizar_cdi_do_bcb', fake_refresh)
    try:
        response = client.post('/v1/financeiro/cdi/refresh')
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_admin, None)
        db_session.close()
        engine.dispose()

    assert response.status_code == 200
    assert response.json()['data']['reference_date'] == '2026-07-03'

    eventos = db_session.query(AuditoriaEvento).all()
    assert len(eventos) == 1
    assert eventos[0].acao == 'CDI_REFRESH_SUCESSO'
    assert eventos[0].usuario == 'analista@empresa.com'
    assert eventos[0].entidade_id == '2026-07-03'
