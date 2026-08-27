"""memoria persistente do Copilot com sincronizacao Planner/Excel (#1359)

Revision ID: c1f4a8d29e73
Revises: 7a1c9e4b2d6f
Create Date: 2026-08-27 07:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1f4a8d29e73'
down_revision: Union[str, Sequence[str], None] = '7a1c9e4b2d6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'copilot_memory_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('memory_id', sa.String(length=64), nullable=False),
        sa.Column('planner_task_id', sa.String(length=200), nullable=True),
        sa.Column('assunto', sa.String(length=500), nullable=False),
        sa.Column('contexto', sa.Text(), nullable=False),
        sa.Column('estado_atual', sa.Text(), nullable=False),
        sa.Column('decisao', sa.Text(), nullable=False),
        sa.Column('pendencia', sa.Text(), nullable=False),
        sa.Column('proximo_passo', sa.Text(), nullable=False),
        sa.Column('fonte_url', sa.Text(), nullable=False),
        sa.Column('data_fonte', sa.String(length=40), nullable=False),
        sa.Column('validade', sa.String(length=30), nullable=False),
        sa.Column('planner_titulo', sa.String(length=500), nullable=False),
        sa.Column('planner_status', sa.String(length=50), nullable=False),
        sa.Column('planner_percentual', sa.Integer(), nullable=False),
        sa.Column('planner_prazo', sa.String(length=40), nullable=False),
        sa.Column('ultima_origem', sa.String(length=30), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('versao', sa.Integer(), nullable=False),
        sa.Column('correlation_id', sa.String(length=80), nullable=False),
        sa.Column('atualizar_planner', sa.Boolean(), nullable=False),
        sa.Column('planner_sync_status', sa.String(length=30), nullable=False),
        sa.Column('planner_applied_hash', sa.String(length=64), nullable=False),
        sa.Column('ultimo_erro', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_copilot_memory_records_criado_em'), 'copilot_memory_records', ['criado_em'], unique=False)
    op.create_index(op.f('ix_copilot_memory_records_memory_id'), 'copilot_memory_records', ['memory_id'], unique=True)
    op.create_index(op.f('ix_copilot_memory_records_planner_task_id'), 'copilot_memory_records', ['planner_task_id'], unique=True)
    op.create_index(op.f('ix_copilot_memory_records_validade'), 'copilot_memory_records', ['validade'], unique=False)
    op.create_index(op.f('ix_copilot_memory_records_ultima_origem'), 'copilot_memory_records', ['ultima_origem'], unique=False)
    op.create_index(op.f('ix_copilot_memory_records_content_hash'), 'copilot_memory_records', ['content_hash'], unique=False)
    op.create_index(op.f('ix_copilot_memory_records_correlation_id'), 'copilot_memory_records', ['correlation_id'], unique=False)
    op.create_index(op.f('ix_copilot_memory_records_atualizar_planner'), 'copilot_memory_records', ['atualizar_planner'], unique=False)
    op.create_index(op.f('ix_copilot_memory_records_planner_sync_status'), 'copilot_memory_records', ['planner_sync_status'], unique=False)

    op.create_table(
        'copilot_memory_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('memory_id', sa.String(length=64), nullable=False),
        sa.Column('versao', sa.Integer(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('origem', sa.String(length=30), nullable=False),
        sa.Column('correlation_id', sa.String(length=80), nullable=False),
        sa.Column('snapshot_json', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_copilot_memory_history_criado_em'), 'copilot_memory_history', ['criado_em'], unique=False)
    op.create_index(op.f('ix_copilot_memory_history_memory_id'), 'copilot_memory_history', ['memory_id'], unique=False)
    op.create_index(op.f('ix_copilot_memory_history_content_hash'), 'copilot_memory_history', ['content_hash'], unique=False)
    op.create_index(op.f('ix_copilot_memory_history_origem'), 'copilot_memory_history', ['origem'], unique=False)
    op.create_index(op.f('ix_copilot_memory_history_correlation_id'), 'copilot_memory_history', ['correlation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_copilot_memory_history_correlation_id'), table_name='copilot_memory_history')
    op.drop_index(op.f('ix_copilot_memory_history_origem'), table_name='copilot_memory_history')
    op.drop_index(op.f('ix_copilot_memory_history_content_hash'), table_name='copilot_memory_history')
    op.drop_index(op.f('ix_copilot_memory_history_memory_id'), table_name='copilot_memory_history')
    op.drop_index(op.f('ix_copilot_memory_history_criado_em'), table_name='copilot_memory_history')
    op.drop_table('copilot_memory_history')

    op.drop_index(op.f('ix_copilot_memory_records_planner_sync_status'), table_name='copilot_memory_records')
    op.drop_index(op.f('ix_copilot_memory_records_atualizar_planner'), table_name='copilot_memory_records')
    op.drop_index(op.f('ix_copilot_memory_records_correlation_id'), table_name='copilot_memory_records')
    op.drop_index(op.f('ix_copilot_memory_records_content_hash'), table_name='copilot_memory_records')
    op.drop_index(op.f('ix_copilot_memory_records_ultima_origem'), table_name='copilot_memory_records')
    op.drop_index(op.f('ix_copilot_memory_records_validade'), table_name='copilot_memory_records')
    op.drop_index(op.f('ix_copilot_memory_records_planner_task_id'), table_name='copilot_memory_records')
    op.drop_index(op.f('ix_copilot_memory_records_memory_id'), table_name='copilot_memory_records')
    op.drop_index(op.f('ix_copilot_memory_records_criado_em'), table_name='copilot_memory_records')
    op.drop_table('copilot_memory_records')
