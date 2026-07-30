"""destinatarios dinamicos do Teams Gateway

Revision ID: 9b6c4d1e7a2f
Revises: 48fc3dc3b06f
Create Date: 2026-07-30 12:23:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9b6c4d1e7a2f'
down_revision: Union[str, Sequence[str], None] = '48fc3dc3b06f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'teams_notification_recipients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('politica', sa.String(length=120), nullable=False),
        sa.Column('nome', sa.String(length=200), nullable=False),
        sa.Column('destino_id', sa.String(length=500), nullable=False),
        sa.Column('destino_tipo', sa.String(length=30), nullable=False),
        sa.Column('prioridade', sa.Integer(), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False),
        sa.Column('observacao', sa.String(length=500), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'politica',
            'destino_tipo',
            'destino_id',
            name='uq_teams_notification_recipient_policy_destination',
        ),
    )
    op.create_index(
        op.f('ix_teams_notification_recipients_ativo'),
        'teams_notification_recipients',
        ['ativo'],
        unique=False,
    )
    op.create_index(
        op.f('ix_teams_notification_recipients_criado_em'),
        'teams_notification_recipients',
        ['criado_em'],
        unique=False,
    )
    op.create_index(
        op.f('ix_teams_notification_recipients_politica'),
        'teams_notification_recipients',
        ['politica'],
        unique=False,
    )
    op.create_index(
        op.f('ix_teams_notification_recipients_prioridade'),
        'teams_notification_recipients',
        ['prioridade'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_teams_notification_recipients_prioridade'), table_name='teams_notification_recipients')
    op.drop_index(op.f('ix_teams_notification_recipients_politica'), table_name='teams_notification_recipients')
    op.drop_index(op.f('ix_teams_notification_recipients_criado_em'), table_name='teams_notification_recipients')
    op.drop_index(op.f('ix_teams_notification_recipients_ativo'), table_name='teams_notification_recipients')
    op.drop_table('teams_notification_recipients')
