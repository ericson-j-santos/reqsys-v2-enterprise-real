from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'g6c9d1e42b83'
down_revision: str | Sequence[str] | None = 'f5b8c0d31a72'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('ai_conversations') as batch:
        batch.add_column(sa.Column('tenant_id', sa.String(length=120), nullable=True))
        batch.add_column(sa.Column('area_id', sa.String(length=120), nullable=True))
        batch.add_column(sa.Column('requester_id', sa.String(length=160), nullable=True))
        batch.add_column(sa.Column('cost_center', sa.String(length=120), nullable=True))

    op.execute(
        sa.text(
            "UPDATE ai_conversations SET "
            "tenant_id='legacy', area_id='legacy', requester_id='legacy-system', cost_center='legacy' "
            "WHERE tenant_id IS NULL OR area_id IS NULL OR requester_id IS NULL OR cost_center IS NULL"
        )
    )

    with op.batch_alter_table('ai_conversations') as batch:
        for name in ('tenant_id', 'area_id', 'requester_id', 'cost_center'):
            batch.alter_column(name, nullable=False)
        batch.create_index('ix_ai_conversations_tenant_id', ['tenant_id'])
        batch.create_index('ix_ai_conversations_area_id', ['area_id'])
        batch.create_index('ix_ai_conversations_requester_id', ['requester_id'])
        batch.create_index('ix_ai_conversations_cost_center', ['cost_center'])

    op.create_table(
        'ai_usage_ledger',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('conversation_id', sa.String(length=36), sa.ForeignKey('ai_conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.String(length=120), nullable=False),
        sa.Column('requester_id', sa.String(length=160), nullable=False),
        sa.Column('cost_center', sa.String(length=120), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('model', sa.String(length=160), nullable=False),
        sa.Column('correlation_id', sa.String(length=160), nullable=False),
        sa.Column('estimated_input_tokens', sa.Integer(), nullable=False),
        sa.Column('estimated_output_tokens', sa.Integer(), nullable=False),
        sa.Column('total_estimated_tokens', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in (
        'conversation_id', 'tenant_id', 'requester_id', 'cost_center',
        'provider', 'model', 'correlation_id', 'criado_em',
    ):
        op.create_index(f'ix_ai_usage_ledger_{column}', 'ai_usage_ledger', [column])


def downgrade() -> None:
    for column in reversed((
        'conversation_id', 'tenant_id', 'requester_id', 'cost_center',
        'provider', 'model', 'correlation_id', 'criado_em',
    )):
        op.drop_index(f'ix_ai_usage_ledger_{column}', table_name='ai_usage_ledger')
    op.drop_table('ai_usage_ledger')

    with op.batch_alter_table('ai_conversations') as batch:
        batch.drop_index('ix_ai_conversations_cost_center')
        batch.drop_index('ix_ai_conversations_requester_id')
        batch.drop_index('ix_ai_conversations_area_id')
        batch.drop_index('ix_ai_conversations_tenant_id')
        batch.drop_column('cost_center')
        batch.drop_column('requester_id')
        batch.drop_column('area_id')
        batch.drop_column('tenant_id')
