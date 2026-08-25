"""rag chunk embeddings (retriever semantico persistente)

Revision ID: e8076bcae516
Revises: 9b6c4d1e7a2f
Create Date: 2026-08-25 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8076bcae516'
down_revision: Union[str, Sequence[str], None] = '9b6c4d1e7a2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'rag_chunk_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chunk_id', sa.String(length=300), nullable=False),
        sa.Column('documento_id', sa.String(length=200), nullable=False),
        sa.Column('titulo', sa.String(length=300), nullable=False),
        sa.Column('origem', sa.String(length=500), nullable=False),
        sa.Column('conteudo', sa.Text(), nullable=False),
        sa.Column('indice', sa.Integer(), nullable=False),
        sa.Column('versao', sa.String(length=32), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chunk_id', name='uq_rag_chunk_embeddings_chunk_id'),
    )
    op.create_index(
        op.f('ix_rag_chunk_embeddings_chunk_id'),
        'rag_chunk_embeddings',
        ['chunk_id'],
        unique=True,
    )
    op.create_index(
        op.f('ix_rag_chunk_embeddings_documento_id'),
        'rag_chunk_embeddings',
        ['documento_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_rag_chunk_embeddings_versao'),
        'rag_chunk_embeddings',
        ['versao'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_rag_chunk_embeddings_versao'), table_name='rag_chunk_embeddings')
    op.drop_index(op.f('ix_rag_chunk_embeddings_documento_id'), table_name='rag_chunk_embeddings')
    op.drop_index(op.f('ix_rag_chunk_embeddings_chunk_id'), table_name='rag_chunk_embeddings')
    op.drop_table('rag_chunk_embeddings')
