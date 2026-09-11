from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f5b8c0d31a72'
down_revision: str | Sequence[str] | None = 'd4a7b9c2e6f1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _lock(conversation_id: str, classification: str) -> str:
    return hashlib.sha256(f'{conversation_id}|{classification}'.encode('utf-8')).hexdigest()


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('ai_conversations')]

    if 'data_classification' not in columns:
        with op.batch_alter_table('ai_conversations') as batch:
            batch.add_column(sa.Column('data_classification', sa.String(length=20), nullable=True))
            batch.add_column(sa.Column('classification_lock_sha256', sa.String(length=64), nullable=True))
            batch.add_column(sa.Column('requested_provider', sa.String(length=30), nullable=True))
            batch.add_column(sa.Column('authorized_provider', sa.String(length=30), nullable=True))
            batch.add_column(sa.Column('policy_mode', sa.String(length=20), nullable=True))
            batch.add_column(sa.Column('policy_decision', sa.String(length=20), nullable=True))
            batch.add_column(sa.Column('policy_reason', sa.String(length=500), nullable=True))
            batch.add_column(sa.Column('policy_correlation_id', sa.String(length=160), nullable=True))

        connection = op.get_bind()
        rows = connection.execute(
            sa.text('SELECT id, provider, correlation_id FROM ai_conversations')
        ).mappings()
        for row in rows:
            classification = 'internal'
            connection.execute(
                sa.text(
                    'UPDATE ai_conversations SET '
                    'data_classification=:classification, '
                    'classification_lock_sha256=:lock_sha, '
                    'requested_provider=:provider, authorized_provider=:provider, '
                    'policy_mode=:policy_mode, policy_decision=:decision, '
                    'policy_reason=:reason, policy_correlation_id=:correlation_id '
                    'WHERE id=:id'
                ),
                {
                    'classification': classification,
                    'lock_sha': _lock(str(row['id']), classification),
                    'provider': row['provider'],
                    'policy_mode': 'off',
                    'decision': 'allowed',
                    'reason': 'migrated_legacy_conversation',
                    'correlation_id': row['correlation_id'],
                    'id': row['id'],
                },
            )

        with op.batch_alter_table('ai_conversations') as batch:
            for name in (
                'data_classification',
                'classification_lock_sha256',
                'requested_provider',
                'authorized_provider',
                'policy_mode',
                'policy_decision',
                'policy_reason',
                'policy_correlation_id',
            ):
                batch.alter_column(name, nullable=False)
            batch.create_index('ix_ai_conversations_data_classification', ['data_classification'])
            batch.create_index('ix_ai_conversations_classification_lock_sha256', ['classification_lock_sha256'])
            batch.create_index('ix_ai_conversations_requested_provider', ['requested_provider'])
            batch.create_index('ix_ai_conversations_authorized_provider', ['authorized_provider'])
            batch.create_index('ix_ai_conversations_policy_mode', ['policy_mode'])
            batch.create_index('ix_ai_conversations_policy_decision', ['policy_decision'])
            batch.create_index('ix_ai_conversations_policy_correlation_id', ['policy_correlation_id'])


def downgrade() -> None:
    with op.batch_alter_table('ai_conversations') as batch:
        batch.drop_index('ix_ai_conversations_policy_correlation_id')
        batch.drop_index('ix_ai_conversations_policy_decision')
        batch.drop_index('ix_ai_conversations_policy_mode')
        batch.drop_index('ix_ai_conversations_authorized_provider')
        batch.drop_index('ix_ai_conversations_requested_provider')
        batch.drop_index('ix_ai_conversations_classification_lock_sha256')
        batch.drop_index('ix_ai_conversations_data_classification')
        batch.drop_column('policy_correlation_id')
        batch.drop_column('policy_reason')
        batch.drop_column('policy_decision')
        batch.drop_column('policy_mode')
        batch.drop_column('authorized_provider')
        batch.drop_column('requested_provider')
        batch.drop_column('classification_lock_sha256')
        batch.drop_column('data_classification')
