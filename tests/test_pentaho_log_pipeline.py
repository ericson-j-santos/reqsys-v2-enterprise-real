from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.pentaho_log_pipeline.pipeline import (
    LogItem,
    archive_log,
    build_idempotency_key,
    purge_log,
    sha256_file,
)


def _item(source: Path, *, execution_id: str = "11111111-1111-1111-1111-111111111111") -> LogItem:
    return LogItem(
        fila_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        execucao_id=execution_id,
        correlation_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        processo="CARGA_CLIENTES",
        iniciado_em=datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc),
        log_caminho=str(source),
        log_sha256=sha256_file(source),
        tamanho_bytes=source.stat().st_size,
        tentativa=1,
    )


def test_idempotency_key_e_estavel_e_depende_da_execucao() -> None:
    digest = "a" * 64
    first = build_idempotency_key("JOB_A", "exec-001", digest)
    replay = build_idempotency_key("JOB_A", "exec-001", digest)
    other_execution = build_idempotency_key("JOB_A", "exec-002", digest)

    assert first == replay
    assert first != other_execution
    assert len(first) == 64


def test_archive_move_para_particao_e_valida_hash(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    archive_root = tmp_path / "archive"
    raw_root.mkdir()
    source = raw_root / "job.log"
    source.write_bytes(b"linha 1\nlinha 2\n")
    item = _item(source)

    destination = archive_log(item, raw_root, archive_root)

    assert destination == archive_root / "2026" / "09" / "14" / f"{item.execucao_id}_job.log"
    assert not source.exists()
    assert destination.exists()
    assert sha256_file(destination) == item.log_sha256


def test_archive_reexecucao_e_idempotente(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    archive_root = tmp_path / "archive"
    raw_root.mkdir()
    source = raw_root / "job.log"
    payload = b"conteudo estavel\n"
    source.write_bytes(payload)
    item = _item(source)

    first = archive_log(item, raw_root, archive_root)
    second = archive_log(item, raw_root, archive_root)

    assert first == second
    assert first.read_bytes() == payload
    assert not source.exists()


def test_archive_recupera_crash_apos_destino_ser_criado(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    archive_root = tmp_path / "archive"
    raw_root.mkdir()
    source = raw_root / "job.log"
    payload = b"mesmo log\n"
    source.write_bytes(payload)
    item = _item(source)
    destination = archive_log(item, raw_root, archive_root)

    # Simula crash após persistir o destino, mas antes de consolidar o estado SQL.
    source.write_bytes(payload)
    recovered = archive_log(item, raw_root, archive_root)

    assert recovered == destination
    assert not source.exists()
    assert destination.read_bytes() == payload


def test_archive_bloqueia_caminho_fora_da_raiz(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    archive_root = tmp_path / "archive"
    outside = tmp_path / "fora.log"
    raw_root.mkdir()
    outside.write_bytes(b"nao mover\n")
    item = _item(outside)

    with pytest.raises(ValueError, match="fora da raiz"):
        archive_log(item, raw_root, archive_root)

    assert outside.exists()


def test_archive_bloqueia_log_alterado_depois_do_ingresso(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    archive_root = tmp_path / "archive"
    raw_root.mkdir()
    source = raw_root / "job.log"
    source.write_bytes(b"original\n")
    item = _item(source)
    source.write_bytes(b"alterado\n")

    with pytest.raises(RuntimeError, match="mudou após ingresso"):
        archive_log(item, raw_root, archive_root)

    assert source.exists()


def test_expurgo_confere_hash_e_e_idempotente(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    target = archive_root / "log.log"
    target.write_bytes(b"conteudo\n")
    digest = sha256_file(target)

    with pytest.raises(RuntimeError, match="expurgo bloqueado"):
        purge_log(target, archive_root, "0" * 64)
    assert target.exists()

    assert purge_log(target, archive_root, digest) is True
    assert not target.exists()
    assert purge_log(target, archive_root, digest) is False
