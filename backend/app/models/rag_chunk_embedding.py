from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RagChunkEmbedding(Base):
    __tablename__ = 'rag_chunk_embeddings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    documento_id: Mapped[str] = mapped_column(String(200), index=True)
    titulo: Mapped[str] = mapped_column(String(300))
    origem: Mapped[str] = mapped_column(String(500))
    conteudo: Mapped[str] = mapped_column(Text)
    indice: Mapped[int] = mapped_column(Integer)
    versao: Mapped[str] = mapped_column(String(32), index=True)
    embedding: Mapped[list[float]] = mapped_column(JSON)
    embedding_provider: Mapped[str] = mapped_column(String(64), default='hash-local-256', server_default='hash-local-256', index=True)
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
