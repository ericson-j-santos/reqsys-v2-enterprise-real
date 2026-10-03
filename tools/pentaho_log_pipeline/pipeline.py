from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LEASE_SECONDS = 300
DEFAULT_RETRY_SECONDS = 120
DEFAULT_RETENTION_DAYS = 30
DEFAULT_BATCH_SIZE = 3


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def emit(event: str, *, level: str = "INFO", **fields: Any) -> None:
    payload = {
        "ts": utc_now().isoformat(),
        "level": level,
        "event": event,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def sanitize_error(exc: BaseException, limit: int = 900) -> str:
    text = " ".join(str(exc).split())
    return text[:limit] if text else exc.__class__.__name__


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def build_idempotency_key(process_name: str, execution_key: str, digest: str) -> str:
    raw = f"{process_name.strip()}|{execution_key.strip()}|{digest.lower()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def ensure_inside(path: Path, root: Path) -> Path:
    resolved_path = path.expanduser().resolve(strict=False)
    resolved_root = root.expanduser().resolve(strict=False)
    if not _is_relative_to(resolved_path, resolved_root):
        raise ValueError(f"caminho fora da raiz permitida: {resolved_path}")
    return resolved_path


def parse_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass(frozen=True)
class LogItem:
    fila_id: str
    execucao_id: str
    correlation_id: str
    processo: str
    iniciado_em: datetime
    log_caminho: str
    log_sha256: str
    tamanho_bytes: int
    tentativa: int


class SqlServerQueue:
    """Adaptador SQL Server.

    A importação de pyodbc é tardia para permitir que os testes das regras de
    arquivo sejam executados sem driver ODBC instalado.
    """

    def __init__(self, connection_string: str) -> None:
        if not connection_string.strip():
            raise ValueError("PENTAHO_LOG_SQLSERVER_CONNECTION não configurada")
        try:
            import pyodbc  # type: ignore
        except ImportError as exc:  # pragma: no cover - depende do host Linux
            raise RuntimeError("pyodbc não instalado; execute pip install -r requirements.txt") from exc
        self._pyodbc = pyodbc
        self._connection_string = connection_string

    def _execute_rows(self, statement: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        connection = self._pyodbc.connect(self._connection_string, autocommit=False)
        try:
            cursor = connection.cursor()
            cursor.execute(statement, *params)
            rows: list[dict[str, Any]] = []
            if cursor.description:
                columns = [column[0] for column in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            connection.commit()
            return rows
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ingest(self, record: dict[str, Any], lote_id: str) -> list[dict[str, Any]]:
        payload = json.dumps([record], ensure_ascii=False, separators=(",", ":"))
        return self._execute_rows(
            "EXEC dbo.sp_pentaho_log_ingestir_json @lote_id=?, @payload=?",
            (lote_id, payload),
        )

    def reserve(self, consumer: str, quantity: int, lease_seconds: int) -> list[LogItem]:
        rows = self._execute_rows(
            "EXEC dbo.sp_pentaho_log_reservar @consumidor=?, @quantidade=?, @lease_segundos=?",
            (consumer, quantity, lease_seconds),
        )
        return [
            LogItem(
                fila_id=str(row["fila_id"]),
                execucao_id=str(row["execucao_id"]),
                correlation_id=str(row["correlation_id"]),
                processo=str(row["processo"]),
                iniciado_em=parse_datetime(row["iniciado_em"]),
                log_caminho=str(row["log_caminho"]),
                log_sha256=str(row["log_sha256"]).lower(),
                tamanho_bytes=int(row["tamanho_bytes"]),
                tentativa=int(row["tentativa"]),
            )
            for row in rows
        ]

    def complete(self, fila_id: str, consumer: str, archive_path: Path, retention_days: int) -> None:
        self._execute_rows(
            "EXEC dbo.sp_pentaho_log_concluir @fila_id=?, @consumidor=?, @arquivo_destino=?, @retencao_dias=?",
            (fila_id, consumer, str(archive_path), retention_days),
        )

    def fail(self, fila_id: str, consumer: str, error: str, retry_seconds: int) -> list[dict[str, Any]]:
        return self._execute_rows(
            "EXEC dbo.sp_pentaho_log_falhar @fila_id=?, @consumidor=?, @erro=?, @retry_segundos=?",
            (fila_id, consumer, error, retry_seconds),
        )

    def reserve_purge(self, consumer: str, quantity: int, lease_seconds: int) -> list[dict[str, Any]]:
        return self._execute_rows(
            "EXEC dbo.sp_pentaho_log_reservar_expurgo @consumidor=?, @quantidade=?, @lease_segundos=?",
            (consumer, quantity, lease_seconds),
        )

    def complete_purge(self, fila_id: str, consumer: str) -> None:
        self._execute_rows(
            "EXEC dbo.sp_pentaho_log_concluir_expurgo @fila_id=?, @consumidor=?",
            (fila_id, consumer),
        )

    def fail_purge(self, fila_id: str, consumer: str, error: str, retry_seconds: int) -> None:
        self._execute_rows(
            "EXEC dbo.sp_pentaho_log_falhar_expurgo @fila_id=?, @consumidor=?, @erro=?, @retry_segundos=?",
            (fila_id, consumer, error, retry_seconds),
        )


def archive_destination(item: LogItem, archive_root: Path) -> Path:
    started = parse_datetime(item.iniciado_em)
    partition = Path(f"{started.year:04d}") / f"{started.month:02d}" / f"{started.day:02d}"
    original_name = Path(item.log_caminho).name
    return archive_root / partition / f"{item.execucao_id}_{original_name}"


def archive_log(item: LogItem, source_root: Path, archive_root: Path) -> Path:
    source = ensure_inside(Path(item.log_caminho), source_root)
    destination = ensure_inside(archive_destination(item, archive_root), archive_root)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        if destination.stat().st_size != item.tamanho_bytes:
            raise RuntimeError("destino existente com tamanho divergente")
        if sha256_file(destination) != item.log_sha256:
            raise RuntimeError("destino existente com SHA-256 divergente")
        if source.exists():
            if source.stat().st_size != item.tamanho_bytes or sha256_file(source) != item.log_sha256:
                raise RuntimeError("origem reapareceu com conteúdo divergente")
            source.unlink()
        return destination

    if not source.exists():
        raise FileNotFoundError(f"log de origem não encontrado: {source}")
    if source.stat().st_size != item.tamanho_bytes:
        raise RuntimeError("tamanho do log mudou após ingresso na fila")
    if sha256_file(source) != item.log_sha256:
        raise RuntimeError("SHA-256 do log mudou após ingresso na fila")

    temp_path = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.part")
    try:
        with source.open("rb") as src, temp_path.open("xb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())
        shutil.copystat(source, temp_path, follow_symlinks=True)
        if temp_path.stat().st_size != item.tamanho_bytes or sha256_file(temp_path) != item.log_sha256:
            raise RuntimeError("cópia de arquivo não preservou tamanho/SHA-256")
        os.replace(temp_path, destination)
        source.unlink()
    finally:
        if temp_path.exists():
            temp_path.unlink()

    if not destination.exists() or sha256_file(destination) != item.log_sha256:
        raise RuntimeError("validação independente do arquivo arquivado falhou")
    return destination


def purge_log(archive_path: Path, archive_root: Path, expected_digest: str) -> bool:
    target = ensure_inside(archive_path, archive_root)
    if not target.exists():
        return False
    if sha256_file(target) != expected_digest.lower():
        raise RuntimeError("SHA-256 do arquivo arquivado diverge; expurgo bloqueado")
    target.unlink()
    if target.exists():
        raise RuntimeError("arquivo ainda existe após tentativa de expurgo")
    return True


def build_record(args: argparse.Namespace) -> dict[str, Any]:
    log_path = Path(args.log).expanduser().resolve(strict=True)
    digest = sha256_file(log_path)
    stat = log_path.stat()
    execution_id = args.execution_id or str(uuid.uuid4())
    correlation_id = args.correlation_id or str(uuid.uuid4())
    execution_key = args.execution_key or f"{args.processo}:{log_path.name}:{stat.st_mtime_ns}:{stat.st_size}"
    idempotency_key = build_idempotency_key(args.processo, execution_key, digest)
    started_at = parse_datetime(args.started_at) if args.started_at else utc_now()
    finished_at = parse_datetime(args.finished_at) if args.finished_at else utc_now()
    exit_code = int(args.exit_code)
    return {
        "execucao_id": execution_id,
        "correlation_id": correlation_id,
        "processo": args.processo,
        "execution_key": execution_key,
        "idempotency_key": idempotency_key,
        "iniciado_em": started_at.isoformat(),
        "finalizado_em": finished_at.isoformat(),
        "exit_code": exit_code,
        "estado_execucao": "SUCESSO" if exit_code == 0 else "FALHA",
        "log_caminho": str(log_path),
        "log_sha256": digest,
        "tamanho_bytes": stat.st_size,
        "host": socket.gethostname(),
    }


def repository_from_env() -> SqlServerQueue:
    return SqlServerQueue(os.getenv("PENTAHO_LOG_SQLSERVER_CONNECTION", ""))


def consume_once(
    repository: SqlServerQueue,
    *,
    consumer: str,
    source_root: Path,
    archive_root: Path,
    quantity: int,
    lease_seconds: int,
    retry_seconds: int,
    retention_days: int,
) -> int:
    reserved = repository.reserve(consumer, quantity, lease_seconds)
    for item in reserved:
        try:
            destination = archive_log(item, source_root, archive_root)
            repository.complete(item.fila_id, consumer, destination, retention_days)
            emit(
                "pentaho_log_concluido",
                fila_id=item.fila_id,
                execucao_id=item.execucao_id,
                correlation_id=item.correlation_id,
                tentativa=item.tentativa,
                destino=str(destination),
            )
        except Exception as exc:  # noqa: BLE001 - fronteira operacional do worker
            error = sanitize_error(exc)
            result = repository.fail(item.fila_id, consumer, error, retry_seconds)
            emit(
                "pentaho_log_falha",
                level="ERROR",
                fila_id=item.fila_id,
                execucao_id=item.execucao_id,
                correlation_id=item.correlation_id,
                tentativa=item.tentativa,
                erro=error,
                estado=(result[0].get("estado") if result else None),
            )
    return len(reserved)


def purge_once(
    repository: SqlServerQueue,
    *,
    consumer: str,
    archive_root: Path,
    quantity: int,
    lease_seconds: int,
    retry_seconds: int,
) -> int:
    rows = repository.reserve_purge(consumer, quantity, lease_seconds)
    for row in rows:
        fila_id = str(row["fila_id"])
        try:
            path = Path(str(row["arquivo_destino"]))
            digest = str(row["log_sha256"]).lower()
            removed = purge_log(path, archive_root, digest)
            repository.complete_purge(fila_id, consumer)
            emit(
                "pentaho_log_expurgado",
                fila_id=fila_id,
                execucao_id=str(row["execucao_id"]),
                correlation_id=str(row["correlation_id"]),
                arquivo=str(path),
                arquivo_existia=removed,
            )
        except Exception as exc:  # noqa: BLE001
            error = sanitize_error(exc)
            repository.fail_purge(fila_id, consumer, error, retry_seconds)
            emit("pentaho_log_expurgo_falha", level="ERROR", fila_id=fila_id, erro=error)
    return len(rows)


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("valor deve ser maior que zero")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline governado de logs Pentaho")
    sub = parser.add_subparsers(dest="command", required=True)

    enqueue = sub.add_parser("enqueue", help="registra um log concluído na fila")
    enqueue.add_argument("--processo", required=True)
    enqueue.add_argument("--log", required=True)
    enqueue.add_argument("--exit-code", default=0, type=int)
    enqueue.add_argument("--execution-id")
    enqueue.add_argument("--correlation-id")
    enqueue.add_argument("--execution-key")
    enqueue.add_argument("--started-at")
    enqueue.add_argument("--finished-at")
    enqueue.add_argument("--lote-id")

    worker = sub.add_parser("worker", help="arquiva logs reservados na fila")
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--poll-seconds", type=positive_int, default=5)
    worker.add_argument("--batch-size", type=positive_int, default=DEFAULT_BATCH_SIZE)
    worker.add_argument("--lease-seconds", type=positive_int, default=DEFAULT_LEASE_SECONDS)
    worker.add_argument("--retry-seconds", type=positive_int, default=DEFAULT_RETRY_SECONDS)
    worker.add_argument("--retention-days", type=positive_int, default=DEFAULT_RETENTION_DAYS)
    worker.add_argument("--consumer")

    purge = sub.add_parser("purge", help="expurga arquivos cuja retenção venceu")
    purge.add_argument("--once", action="store_true")
    purge.add_argument("--poll-seconds", type=positive_int, default=60)
    purge.add_argument("--batch-size", type=positive_int, default=DEFAULT_BATCH_SIZE)
    purge.add_argument("--lease-seconds", type=positive_int, default=DEFAULT_LEASE_SECONDS)
    purge.add_argument("--retry-seconds", type=positive_int, default=DEFAULT_RETRY_SECONDS)
    purge.add_argument("--consumer")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = repository_from_env()

    if args.command == "enqueue":
        record = build_record(args)
        lote_id = args.lote_id or str(uuid.uuid4())
        rows = repository.ingest(record, lote_id)
        emit(
            "pentaho_log_ingresso",
            lote_id=lote_id,
            execucao_id=record["execucao_id"],
            correlation_id=record["correlation_id"],
            idempotency_key=record["idempotency_key"],
            resultado=rows,
        )
        return 0

    source_root = Path(os.getenv("PENTAHO_LOG_ROOT", "/var/log/pentaho"))
    archive_root = Path(os.getenv("PENTAHO_LOG_ARCHIVE_ROOT", "/var/log/pentaho/archive"))
    consumer = args.consumer or f"{socket.gethostname()}:{os.getpid()}:{args.command}"

    if args.command == "worker":
        while True:
            count = consume_once(
                repository,
                consumer=consumer,
                source_root=source_root,
                archive_root=archive_root,
                quantity=args.batch_size,
                lease_seconds=args.lease_seconds,
                retry_seconds=args.retry_seconds,
                retention_days=args.retention_days,
            )
            if args.once:
                return 0
            if count == 0:
                time.sleep(args.poll_seconds)

    if args.command == "purge":
        while True:
            count = purge_once(
                repository,
                consumer=consumer,
                archive_root=archive_root,
                quantity=args.batch_size,
                lease_seconds=args.lease_seconds,
                retry_seconds=args.retry_seconds,
            )
            if args.once:
                return 0
            if count == 0:
                time.sleep(args.poll_seconds)

    return 2


if __name__ == "__main__":
    sys.exit(main())
