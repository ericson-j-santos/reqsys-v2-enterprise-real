"""cerimonias e acoes do Agile Runtime

Revision ID: d4a7b9c2e6f1
Revises: c1f4a8d29e73
Create Date: 2026-09-05 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4a7b9c2e6f1'
down_revision: Union[str, Sequence[str], None] = 'c1f4a8d29e73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'agile_ceremonies' not in tables:
            op.create_table(
        'agile_ceremonies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=40), nullable=False),
        sa.Column('sprint_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=30), nullable=False),
        sa.Column('titulo', sa.String(length=220), nullable=False),
        sa.Column('inicio_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duracao_minutos', sa.Integer(), nullable=False),
        sa.Column('facilitador', sa.String(length=120), nullable=False),
        sa.Column('participantes_json', sa.Text(), nullable=False),
        sa.Column('pauta', sa.Text(), nullable=True),
        sa.Column('resumo', sa.Text(), nullable=True),
        sa.Column('decisoes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('correlation_id', sa.String(length=120), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['sprint_id'], ['agile_sprints.id']),
        sa.PrimaryKeyConstraint('id'),
            )
            op.create_index('ix_agile_ceremonies_codigo', 'agile_ceremonies', ['codigo'], unique=True)
            op.create_index('ix_agile_ceremonies_sprint_id', 'agile_ceremonies', ['sprint_id'])
            op.create_index('ix_agile_ceremonies_inicio_em', 'agile_ceremonies', ['inicio_em'])
            op.create_index('ix_agile_ceremonies_tipo', 'agile_ceremonies', ['tipo'])
            op.create_index('ix_agile_ceremonies_status', 'agile_ceremonies', ['status'])
            op.create_index('ix_agile_ceremonies_correlation_id', 'agile_ceremonies', ['correlation_id'])
            op.create_index('ix_agile_ceremonies_criado_em', 'agile_ceremonies', ['criado_em'])

            op.create_table(
        'agile_ceremony_actions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cerimonia_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=30), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=False),
        sa.Column('responsavel', sa.String(length=120), nullable=False),
        sa.Column('prazo', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('bloqueante', sa.Boolean(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['cerimonia_id'], ['agile_ceremonies.id']),
        sa.PrimaryKeyConstraint('id'),
            )
            op.create_index('ix_agile_ceremony_actions_cerimonia_id', 'agile_ceremony_actions', ['cerimonia_id'])
            op.create_index('ix_agile_ceremony_actions_status', 'agile_ceremony_actions', ['status'])
            op.create_index('ix_agile_ceremony_actions_tipo', 'agile_ceremony_actions', ['tipo'])
            op.create_index('ix_agile_ceremony_actions_criado_em', 'agile_ceremony_actions', ['criado_em'])


def downgrade() -> None:
    op.drop_index('ix_agile_ceremony_actions_status', table_name='agile_ceremony_actions')
    op.drop_index('ix_agile_ceremony_actions_tipo', table_name='agile_ceremony_actions')
    op.drop_index('ix_agile_ceremony_actions_criado_em', table_name='agile_ceremony_actions')
    op.drop_index('ix_agile_ceremony_actions_cerimonia_id', table_name='agile_ceremony_actions')
    op.drop_table('agile_ceremony_actions')
    op.drop_index('ix_agile_ceremonies_inicio_em', table_name='agile_ceremonies')
    op.drop_index('ix_agile_ceremonies_tipo', table_name='agile_ceremonies')
    op.drop_index('ix_agile_ceremonies_status', table_name='agile_ceremonies')
    op.drop_index('ix_agile_ceremonies_correlation_id', table_name='agile_ceremonies')
    op.drop_index('ix_agile_ceremonies_criado_em', table_name='agile_ceremonies')
    op.drop_index('ix_agile_ceremonies_sprint_id', table_name='agile_ceremonies')
    op.drop_index('ix_agile_ceremonies_codigo', table_name='agile_ceremonies')
    op.drop_table('agile_ceremonies')
