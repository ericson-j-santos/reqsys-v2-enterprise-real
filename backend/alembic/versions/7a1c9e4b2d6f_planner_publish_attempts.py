"""tabela de tentativas governadas de publicacao no Planner (issue #32)

Revision ID: 7a1c9e4b2d6f
Revises: 2f236a397adc
Create Date: 2026-08-26 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a1c9e4b2d6f'
down_revision: Union[str, Sequence[str], None] = '2f236a397adc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'planner_publish_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('idempotency_key', sa.String(length=64), nullable=False),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('correlation_id', sa.String(length=80), nullable=False),
        sa.Column('source_id', sa.String(length=200), nullable=False),
        sa.Column('plan_id', sa.String(length=200), nullable=False),
        sa.Column('bucket_id', sa.String(length=200), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('due_date', sa.String(length=40), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.Column('requester', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('tentativas', sa.Integer(), nullable=False),
        sa.Column('planner_task_id', sa.String(length=200), nullable=True),
        sa.Column('ultimo_erro', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_planner_publish_attempts_idempotency_key'),
        'planner_publish_attempts',
        ['idempotency_key'],
        unique=True,
    )
    op.create_index(
        op.f('ix_planner_publish_attempts_criado_em'),
        'planner_publish_attempts',
        ['criado_em'],
        unique=False,
    )
    op.create_index(
        op.f('ix_planner_publish_attempts_correlation_id'),
        'planner_publish_attempts',
        ['correlation_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_planner_publish_attempts_source_id'),
        'planner_publish_attempts',
        ['source_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_planner_publish_attempts_status'),
        'planner_publish_attempts',
        ['status'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_planner_publish_attempts_status'), table_name='planner_publish_attempts')
    op.drop_index(op.f('ix_planner_publish_attempts_source_id'), table_name='planner_publish_attempts')
    op.drop_index(op.f('ix_planner_publish_attempts_correlation_id'), table_name='planner_publish_attempts')
    op.drop_index(op.f('ix_planner_publish_attempts_criado_em'), table_name='planner_publish_attempts')
    op.drop_index(op.f('ix_planner_publish_attempts_idempotency_key'), table_name='planner_publish_attempts')
    op.drop_table('planner_publish_attempts')
