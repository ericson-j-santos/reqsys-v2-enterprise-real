"""rag chunk embedding provider (permite provider externo de embeddings)

Revision ID: 2f236a397adc
Revises: e8076bcae516
Create Date: 2026-08-25 19:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2f236a397adc'
down_revision: Union[str, Sequence[str], None] = 'e8076bcae516'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_PROVIDER = 'hash-local-256'


def upgrade() -> None:
    op.add_column(
        'rag_chunk_embeddings',
        sa.Column('embedding_provider', sa.String(length=64), nullable=False, server_default=_DEFAULT_PROVIDER),
    )
    op.create_index(
        op.f('ix_rag_chunk_embeddings_embedding_provider'),
        'rag_chunk_embeddings',
        ['embedding_provider'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_rag_chunk_embeddings_embedding_provider'), table_name='rag_chunk_embeddings')
    op.drop_column('rag_chunk_embeddings', 'embedding_provider')
