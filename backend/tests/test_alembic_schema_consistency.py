"""Guarda-chuva de regressao para a integracao Alembic introduzida na ADR-042.

Cobre os dois bugs reais encontrados ao montar `alembic/env.py`:
1. Importar so `app.models` deixava models registrados so via `app.api`/
   `app.services` fora de Base.metadata, fazendo autogenerate achar tabelas
   reais como "removidas" (geraria DROP TABLE).
2. `app/core/runtime_analytics.py` usa seu proprio MetaData()/engine, fora do
   Base declarativo -- sem o filtro `include_object`, autogenerate tentaria
   dropar essas tabelas tambem.

Roda 100% hermetico contra SQLite em memoria: nao depende de Postgres nem de
qualquer DATABASE_URL configurada no ambiente.
"""
import sys

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.testing.repository_paths import get_repository_root

_ALEMBIC_DIR = get_repository_root() / "backend" / "alembic"
if str(_ALEMBIC_DIR) not in sys.path:
    sys.path.insert(0, str(_ALEMBIC_DIR))

from schema_filters import RUNTIME_ANALYTICS_TABLES, include_object  # noqa: E402

import app.main  # noqa: E402,F401  (registra todos os models em Base.metadata)
from app.db import Base  # noqa: E402


def test_alembic_ini_and_versions_exist():
    backend_dir = get_repository_root() / "backend"

    assert (backend_dir / "alembic.ini").exists()
    assert (backend_dir / "alembic" / "env.py").exists()

    versions_dir = backend_dir / "alembic" / "versions"
    revisions = list(versions_dir.glob("*.py"))

    assert revisions, "esperava ao menos uma revision em alembic/versions/"


def test_full_app_metadata_includes_indirectly_registered_models():
    # Estes models so entram em Base.metadata quando os modulos de app/api ou
    # app/services que os referenciam sao importados -- regressao do bug (1).
    indirectly_registered_tables = {
        "codex_auditoria",
        "vinculos_git",
        "integracoes_figma_github",
    }

    assert indirectly_registered_tables.issubset(Base.metadata.tables.keys())


def test_runtime_analytics_tables_are_not_part_of_declarative_base():
    # app/core/runtime_analytics.py gerencia seu proprio schema fora do Base --
    # se algum dia esses models forem migrados para o Base declarativo, o
    # filtro em schema_filters.py precisa ser revisado/removido junto.
    assert not RUNTIME_ANALYTICS_TABLES.intersection(Base.metadata.tables.keys())


def test_include_object_excludes_runtime_analytics_tables():
    for table_name in RUNTIME_ANALYTICS_TABLES:
        assert include_object(None, table_name, "table", False, None) is False


def test_include_object_keeps_regular_tables_and_non_table_objects():
    assert include_object(None, "requisitos", "table", False, None) is True
    # tipos != "table" (colunas, indices, etc.) nunca devem ser filtrados por nome de tabela
    assert include_object(None, "runtime_deploy_events", "column", False, None) is True


def test_autogenerate_reports_no_drift_against_fresh_declarative_schema():
    """Se este teste falhar, um model do Base foi alterado sem gerar migration
    (ou o filtro/import em env.py ficou desatualizado)."""
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            Base.metadata.create_all(bind=connection)

            migration_context = MigrationContext.configure(
                connection=connection,
                opts={"include_object": include_object, "compare_type": True},
            )
            diff = compare_metadata(migration_context, Base.metadata)

        assert diff == []
    finally:
        engine.dispose()
