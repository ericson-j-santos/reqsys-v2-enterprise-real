import hashlib

from sqlalchemy import create_engine, inspect, text

from app.services.ai_conversation_schema_repair import reconciliar_schema_ai_conversations


def _partial_engine():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql(
            '''
            CREATE TABLE ai_conversations (
                id VARCHAR(36) PRIMARY KEY,
                provider VARCHAR(30) NOT NULL,
                correlation_id VARCHAR(160),
                data_classification VARCHAR(20)
            )
            '''
        )
        conn.execute(
            text(
                'INSERT INTO ai_conversations '
                '(id, provider, correlation_id, data_classification) '
                'VALUES (:id, :provider, :correlation_id, NULL)'
            ),
            {'id': 'conv-1', 'provider': 'groq', 'correlation_id': 'corr-1'},
        )
    return engine


def test_repara_schema_parcial_e_backfill_sem_perder_dados():
    engine = _partial_engine()

    result = reconciliar_schema_ai_conversations(engine)

    columns = {column['name'] for column in inspect(engine).get_columns('ai_conversations')}
    expected = {
        'data_classification', 'classification_lock_sha256', 'requested_provider',
        'authorized_provider', 'policy_mode', 'policy_decision', 'policy_reason',
        'policy_correlation_id', 'tenant_id', 'area_id', 'requester_id', 'cost_center',
    }
    assert expected <= columns
    assert result['status'] == 'ready'
    assert 'classification_lock_sha256' in result['added_columns']

    with engine.connect() as conn:
        row = conn.execute(text('SELECT * FROM ai_conversations WHERE id=:id'), {'id': 'conv-1'}).mappings().one()

    assert row['provider'] == 'groq'
    assert row['data_classification'] == 'internal'
    assert row['requested_provider'] == 'groq'
    assert row['authorized_provider'] == 'groq'
    assert row['policy_mode'] == 'off'
    assert row['policy_decision'] == 'allowed'
    assert row['tenant_id'] == 'legacy'
    assert row['area_id'] == 'legacy'
    assert row['requester_id'] == 'legacy-system'
    assert row['cost_center'] == 'legacy'
    assert row['classification_lock_sha256'] == hashlib.sha256(b'conv-1|internal').hexdigest()


def test_reparo_e_idempotente():
    engine = _partial_engine()
    reconciliar_schema_ai_conversations(engine)

    second = reconciliar_schema_ai_conversations(engine)

    assert second == {'status': 'ready', 'added_columns': []}


def test_tabela_ausente_nao_e_criada_pelo_reparo():
    engine = create_engine('sqlite+pysqlite:///:memory:')

    result = reconciliar_schema_ai_conversations(engine)

    assert result == {'status': 'table_absent', 'added_columns': []}
    assert 'ai_conversations' not in inspect(engine).get_table_names()
