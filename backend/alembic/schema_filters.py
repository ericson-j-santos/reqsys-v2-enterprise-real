"""Filtros de autogenerate compartilhados entre alembic/env.py e os testes.

Extraido de env.py para ser importavel sem disparar o runtime do Alembic
(env.py executa `context.is_offline_mode()` no import, que exige um
MigrationContext/Config ja ativo).
"""

# app/core/runtime_analytics.py mantem seu proprio MetaData()/engine e faz seu
# proprio create_all, fora do Base declarativo. Sem este filtro, autogenerate
# tentaria dropar essas tabelas reais por nao enxerga-las em Base.metadata.
RUNTIME_ANALYTICS_TABLES = {
    "runtime_deploy_events",
    "runtime_incident_events",
    "runtime_operational_snapshots",
}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in RUNTIME_ANALYTICS_TABLES:
        return False
    return True
