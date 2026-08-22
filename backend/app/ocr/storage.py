"""Persistência protegida de resultados OCR.

PII reconhecida nunca é gravada em texto puro. O payload sensível usa AES-GCM
com chave dedicada resolvida pelo mecanismo central de secrets do ReqSys.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import UTC, datetime
from typing import Callable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import DateTime, Float, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.secrets import get_secret
from app.db import Base, SessionLocal
from app.ocr.worker import OcrResultado

_CHAVE_SEGREDO = 'OCR_DATA_ENCRYPTION_KEY'
_NONCE_BYTES = 12


class OcrResultadoPersistido(Base):
    __tablename__ = 'ocr_resultados'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    tipo_documento: Mapped[str] = mapped_column(String(80), nullable=False)
    campo: Mapped[str] = mapped_column(String(80), nullable=False)
    estado_ocr: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    confianca: Mapped[float] = mapped_column(Float, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    key_version: Mapped[str] = mapped_column(String(40), nullable=False, default='v1')
    payload_protegido: Mapped[str] = mapped_column(Text, nullable=False)
    status_revisao: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    reviewer_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decisao_protegida: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    revisado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OcrDataProtector:
    def __init__(self, key_b64: str | None = None, *, key_version: str | None = None) -> None:
        valor = key_b64 or get_secret(_CHAVE_SEGREDO, prefer_vault=True)
        if not valor:
            raise RuntimeError(f'{_CHAVE_SEGREDO} não configurada')
        try:
            chave = base64.b64decode(valor, validate=True)
        except Exception as exc:
            raise RuntimeError(f'{_CHAVE_SEGREDO} deve ser base64 válido') from exc
        if len(chave) != 32:
            raise RuntimeError(f'{_CHAVE_SEGREDO} deve representar exatamente 32 bytes')
        self._aes = AESGCM(chave)
        self.key_version = key_version or os.getenv('OCR_DATA_KEY_VERSION', 'v1').strip() or 'v1'

    def proteger(self, payload: dict, *, aad: str) -> str:
        nonce = os.urandom(_NONCE_BYTES)
        plaintext = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        ciphertext = self._aes.encrypt(nonce, plaintext, aad.encode('utf-8'))
        return base64.b64encode(nonce + ciphertext).decode('ascii')

    def revelar(self, blob: str, *, aad: str) -> dict:
        try:
            raw = base64.b64decode(blob, validate=True)
            nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
            plaintext = self._aes.decrypt(nonce, ciphertext, aad.encode('utf-8'))
            return json.loads(plaintext.decode('utf-8'))
        except Exception as exc:
            raise RuntimeError('payload OCR protegido inválido ou chave incompatível') from exc


class RepositorioResultadosOcrSqlAlchemy:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        protector: OcrDataProtector | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._protector = protector or OcrDataProtector()

    def salvar(self, resultado: OcrResultado) -> None:
        with self._session_factory() as db:
            existente = db.scalar(select(OcrResultadoPersistido).where(OcrResultadoPersistido.job_id == resultado.job_id))
            if existente is not None:
                return
            status = 'AUTO' if resultado.estado_ocr == 'AUTO' else 'PENDENTE'
            protegido = self._protector.proteger(
                {'valor': resultado.valor, 'motivos': list(resultado.motivos)},
                aad=resultado.job_id,
            )
            db.add(OcrResultadoPersistido(
                job_id=resultado.job_id,
                correlation_id=resultado.correlation_id,
                tipo_documento=resultado.tipo_documento,
                campo=resultado.campo,
                estado_ocr=resultado.estado_ocr,
                confianca=resultado.confianca,
                engine_version=resultado.engine_version,
                key_version=self._protector.key_version,
                payload_protegido=protegido,
                status_revisao=status,
            ))
            db.commit()

    def listar(self, *, status: str | None = None, limite: int = 100) -> list[dict]:
        limite = max(1, min(int(limite), 500))
        with self._session_factory() as db:
            stmt = select(OcrResultadoPersistido).order_by(OcrResultadoPersistido.criado_em.desc()).limit(limite)
            if status:
                stmt = stmt.where(OcrResultadoPersistido.status_revisao == status.upper())
            itens = list(db.scalars(stmt))
            return [self._metadata(item) for item in itens]

    def obter(self, job_id: str, *, revelar_pii: bool = False) -> dict | None:
        with self._session_factory() as db:
            item = db.scalar(select(OcrResultadoPersistido).where(OcrResultadoPersistido.job_id == job_id))
            if item is None:
                return None
            dados = self._metadata(item)
            if revelar_pii:
                sensivel = self._protector.revelar(item.payload_protegido, aad=item.job_id)
                dados['valor'] = sensivel.get('valor')
                dados['motivos'] = sensivel.get('motivos', [])
            return dados

    def decidir(self, job_id: str, *, decisao: str, reviewer: str, observacao: str = '') -> dict:
        decisao = decisao.upper().strip()
        if decisao not in {'APROVADO', 'REJEITADO'}:
            raise ValueError('decisao deve ser APROVADO ou REJEITADO')
        with self._session_factory() as db:
            item = db.scalar(select(OcrResultadoPersistido).where(OcrResultadoPersistido.job_id == job_id))
            if item is None:
                raise LookupError('resultado OCR não encontrado')
            if item.status_revisao != 'PENDENTE':
                raise ValueError(f'resultado não está pendente de revisão: {item.status_revisao}')
            item.status_revisao = decisao
            item.reviewer_hash = hashlib.sha256(reviewer.encode('utf-8')).hexdigest()
            item.decisao_protegida = self._protector.proteger({'observacao': observacao}, aad=f'{job_id}:decisao')
            item.revisado_em = datetime.now(UTC)
            db.commit()
            db.refresh(item)
            return self._metadata(item)

    @staticmethod
    def _metadata(item: OcrResultadoPersistido) -> dict:
        return {
            'job_id': item.job_id,
            'correlation_id': item.correlation_id,
            'tipo_documento': item.tipo_documento,
            'campo': item.campo,
            'estado_ocr': item.estado_ocr,
            'confianca': round(float(item.confianca), 6),
            'engine_version': item.engine_version,
            'key_version': item.key_version,
            'status_revisao': item.status_revisao,
            'criado_em': item.criado_em.isoformat() if item.criado_em else None,
            'revisado_em': item.revisado_em.isoformat() if item.revisado_em else None,
            'pii_exposta': False,
        }


def ocr_store_readiness() -> dict[str, object]:
    segredo = get_secret(_CHAVE_SEGREDO, prefer_vault=True)
    return {
        'schema_version': '1.0.0',
        'encryption': 'AES-256-GCM',
        'key_name': _CHAVE_SEGREDO,
        'key_configured': bool(segredo),
        'key_version': os.getenv('OCR_DATA_KEY_VERSION', 'v1').strip() or 'v1',
        'plaintext_storage_allowed': False,
        'ready': bool(segredo),
    }
