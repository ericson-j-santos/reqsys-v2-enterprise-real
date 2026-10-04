from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.ocr.storage import RepositorioClaimsOcrSqlAlchemy


def _factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ocr-claims.db'}",
        connect_args={'check_same_thread': False},
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_claim_impede_dois_donos_simultaneos(tmp_path):
    engine, factory = _factory(tmp_path)
    try:
        instance_a = RepositorioClaimsOcrSqlAlchemy(session_factory=factory, lease_seconds=60)
        instance_b = RepositorioClaimsOcrSqlAlchemy(session_factory=factory, lease_seconds=60)
        now = datetime.now(UTC)

        assert instance_a.adquirir('job-1', 'owner-a', agora=now) is True
        assert instance_b.adquirir('job-1', 'owner-b', agora=now) is False
        assert instance_b.liberar('job-1', 'owner-b') is False
        assert instance_a.liberar('job-1', 'owner-a') is True
        assert instance_b.adquirir('job-1', 'owner-b', agora=now) is True
    finally:
        engine.dispose()


def test_claim_expirado_pode_ser_reapropriado(tmp_path):
    engine, factory = _factory(tmp_path)
    try:
        first = RepositorioClaimsOcrSqlAlchemy(session_factory=factory, lease_seconds=5)
        second = RepositorioClaimsOcrSqlAlchemy(session_factory=factory, lease_seconds=5)
        t0 = datetime.now(UTC)

        assert first.adquirir('job-expira', 'owner-a', agora=t0) is True
        assert second.adquirir('job-expira', 'owner-b', agora=t0 + timedelta(seconds=4)) is False
        assert second.adquirir('job-expira', 'owner-b', agora=t0 + timedelta(seconds=6)) is True
        assert first.liberar('job-expira', 'owner-a') is False
        assert second.liberar('job-expira', 'owner-b') is True
    finally:
        engine.dispose()


def test_renovacao_estende_lease_somente_para_dono(tmp_path):
    engine, factory = _factory(tmp_path)
    try:
        repo = RepositorioClaimsOcrSqlAlchemy(session_factory=factory, lease_seconds=5)
        contender = RepositorioClaimsOcrSqlAlchemy(session_factory=factory, lease_seconds=5)
        t0 = datetime.now(UTC)

        assert repo.adquirir('job-renova', 'owner-a', agora=t0) is True
        assert repo.renovar('job-renova', 'owner-b', agora=t0 + timedelta(seconds=3)) is False
        assert repo.renovar('job-renova', 'owner-a', agora=t0 + timedelta(seconds=3)) is True
        assert contender.adquirir('job-renova', 'owner-b', agora=t0 + timedelta(seconds=6)) is False
        assert contender.adquirir('job-renova', 'owner-b', agora=t0 + timedelta(seconds=9)) is True
    finally:
        engine.dispose()
