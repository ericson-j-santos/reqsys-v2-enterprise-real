from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pyodbc

from pipeline import SqlServerQueue, sha256_file


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = Path(__file__).resolve().with_name("pipeline.py")
WRAPPER = Path(__file__).resolve().with_name("run_pentaho_with_queue.sh")
PACKAGE = ROOT / "tools" / "gerador_pentaho" / "pacote"
BUSINESS_EVIDENCE = PACKAGE / "saida" / "evidencias_pentaho.csv"
EVIDENCE_DIR = Path(os.environ["PENTAHO_E2E_EVIDENCE_DIR"]).resolve()
RAW_ROOT = Path(os.environ["PENTAHO_LOG_ROOT"]).resolve()
ARCHIVE_ROOT = Path(os.environ["PENTAHO_LOG_ARCHIVE_ROOT"]).resolve()
CONNECTION_STRING = os.environ["PENTAHO_LOG_SQLSERVER_CONNECTION"]
MARKER = os.environ["PENTAHO_E2E_MARKER"]

EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
RAW_ROOT.mkdir(parents=True, exist_ok=True)
ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)


def fail(message: str) -> None:
    raise AssertionError(message)


def run(name: str, command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env or os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    (EVIDENCE_DIR / f"{name}.stdout.log").write_text(result.stdout, encoding="utf-8")
    (EVIDENCE_DIR / f"{name}.stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        fail(f"{name} falhou com rc={result.returncode}")
    return result


def query_one(sql: str, params: tuple[object, ...] = ()) -> tuple[object, ...] | None:
    with pyodbc.connect(CONNECTION_STRING, autocommit=True) as connection:
        cursor = connection.cursor()
        cursor.execute(sql, *params)
        row = cursor.fetchone()
        return tuple(row) if row is not None else None


def query_all(sql: str, params: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    with pyodbc.connect(CONNECTION_STRING, autocommit=True) as connection:
        cursor = connection.cursor()
        cursor.execute(sql, *params)
        return [tuple(row) for row in cursor.fetchall()]


def execute(sql: str, params: tuple[object, ...] = ()) -> None:
    with pyodbc.connect(CONNECTION_STRING, autocommit=True) as connection:
        connection.cursor().execute(sql, *params)


def enqueue_manual(process_name: str, source: Path, execution_id: str, correlation_id: str, execution_key: str) -> None:
    run(
        f"enqueue-{process_name}",
        [
            sys.executable,
            str(PIPELINE),
            "enqueue",
            "--processo",
            process_name,
            "--log",
            str(source),
            "--exit-code",
            "0",
            "--execution-id",
            execution_id,
            "--correlation-id",
            correlation_id,
            "--execution-key",
            execution_key,
        ],
    )


def queue_state(execution_id: str) -> tuple[str, int, str | None, str | None]:
    row = query_one(
        """
        SELECT f.estado, f.tentativas, f.consumidor, f.arquivo_destino
        FROM dbo.pentaho_log_fila AS f
        WHERE f.execucao_id = ?
        """,
        (execution_id,),
    )
    if row is None:
        fail(f"fila ausente para {execution_id}")
    return str(row[0]), int(row[1]), (str(row[2]) if row[2] is not None else None), (str(row[3]) if row[3] is not None else None)


def write_snapshot(name: str) -> None:
    rows = query_all(
        """
        SELECT
            CONVERT(varchar(36), e.execucao_id),
            CONVERT(varchar(36), e.correlation_id),
            e.processo,
            e.execution_key,
            e.log_sha256,
            e.tamanho_bytes,
            f.estado,
            f.tentativas,
            f.consumidor,
            f.arquivo_destino,
            f.retencao_ate,
            f.expurgo_tentativas,
            f.expurgado_em,
            f.ultimo_erro
        FROM dbo.pentaho_log_execucao AS e
        INNER JOIN dbo.pentaho_log_fila AS f ON f.execucao_id = e.execucao_id
        WHERE e.processo LIKE ?
        ORDER BY e.criado_em, e.execucao_id
        """,
        (MARKER + "%",),
    )
    payload = [
        {
            "execucao_id": str(row[0]),
            "correlation_id": str(row[1]),
            "processo": str(row[2]),
            "execution_key": str(row[3]),
            "log_sha256": str(row[4]),
            "tamanho_bytes": int(row[5]),
            "estado": str(row[6]),
            "tentativas": int(row[7]),
            "consumidor": None if row[8] is None else str(row[8]),
            "arquivo_destino": None if row[9] is None else str(row[9]),
            "retencao_ate": None if row[10] is None else str(row[10]),
            "expurgo_tentativas": int(row[11]),
            "expurgado_em": None if row[12] is None else str(row[12]),
            "ultimo_erro": None if row[13] is None else str(row[13]),
        }
        for row in rows
    ]
    (EVIDENCE_DIR / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    pre_count = query_one(
        "SELECT COUNT(*) FROM dbo.pentaho_log_execucao WHERE processo LIKE ?",
        (MARKER + "%",),
    )
    if pre_count is None or int(pre_count[0]) != 0:
        fail("pré-condição violada: banco descartável contém evidência residual")

    if BUSINESS_EVIDENCE.exists():
        BUSINESS_EVIDENCE.unlink()

    wrapper_env = os.environ.copy()
    wrapper_env["PENTAHO_PROCESS_NAME"] = MARKER
    wrapper_result = run("01-wrapper-kitchen-enqueue", ["bash", str(WRAPPER)], env=wrapper_env)

    ingress: dict[str, object] | None = None
    for line in wrapper_result.stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == "pentaho_log_ingresso":
            ingress = payload
    if ingress is None:
        fail("wrapper não publicou evento pentaho_log_ingresso")

    first_execution_id = str(ingress["execucao_id"])
    first_correlation_id = str(ingress["correlation_id"])

    business_text = BUSINESS_EVIDENCE.read_text(encoding="utf-8-sig")
    if "DEM-TREINO-0001" not in business_text or "DOSSIE_CRIADO" not in business_text:
        fail("efeito positivo do job Pentaho não foi observado")
    if "DEM-TREINO-0002" not in business_text or "CRIACAO_RECUSADA" not in business_text:
        fail("efeito negativo/controlado do job Pentaho não foi observado")
    shutil.copy2(BUSINESS_EVIDENCE, EVIDENCE_DIR / "business-evidence.csv")

    row = query_one(
        """
        SELECT e.execution_key, e.log_caminho, e.log_sha256, e.tamanho_bytes, f.estado,
               CONVERT(varchar(36), e.correlation_id)
        FROM dbo.pentaho_log_execucao AS e
        INNER JOIN dbo.pentaho_log_fila AS f ON f.execucao_id = e.execucao_id
        WHERE e.execucao_id = ?
        """,
        (first_execution_id,),
    )
    if row is None:
        fail("execução do wrapper não foi persistida no SQL Server")
    execution_key, raw_path_text, db_digest, db_size, initial_state, sql_correlation = row
    raw_path = Path(str(raw_path_text))
    if str(initial_state) != "AGUARDANDO":
        fail(f"estado inicial inesperado: {initial_state}")
    if str(sql_correlation) != first_correlation_id:
        fail("correlation_id do SQL diverge do evento do produtor")
    if not raw_path.exists():
        fail("log bruto não existe após ingresso")
    if raw_path.stat().st_size != int(db_size) or sha256_file(raw_path) != str(db_digest).lower():
        fail("log bruto diverge dos metadados persistidos")

    run(
        "02-idempotency-repeat",
        [
            sys.executable,
            str(PIPELINE),
            "enqueue",
            "--processo",
            MARKER,
            "--log",
            str(raw_path),
            "--exit-code",
            "0",
            "--execution-id",
            first_execution_id,
            "--correlation-id",
            first_correlation_id,
            "--execution-key",
            str(execution_key),
        ],
    )
    duplicate_counts = query_one(
        """
        SELECT
          (SELECT COUNT(*) FROM dbo.pentaho_log_execucao WHERE execucao_id = ?),
          (SELECT COUNT(*) FROM dbo.pentaho_log_fila WHERE execucao_id = ?)
        """,
        (first_execution_id, first_execution_id),
    )
    if duplicate_counts != (1, 1):
        fail(f"idempotência falhou: {duplicate_counts}")

    run(
        "03-worker-main",
        [
            sys.executable,
            str(PIPELINE),
            "worker",
            "--once",
            "--batch-size",
            "1",
            "--lease-seconds",
            "30",
            "--retry-seconds",
            "3600",
            "--retention-days",
            "1",
            "--consumer",
            "e2e-worker-main",
        ],
    )
    state, attempts, _, archive_path_text = queue_state(first_execution_id)
    if state != "CONCLUIDO" or attempts != 1 or not archive_path_text:
        fail(f"worker principal não concluiu corretamente: {state}/{attempts}/{archive_path_text}")
    archive_path = Path(archive_path_text)
    if raw_path.exists():
        fail("origem permaneceu após arquivamento concluído")
    if not archive_path.exists() or sha256_file(archive_path) != str(db_digest).lower():
        fail("arquivo arquivado ausente ou com SHA divergente")
    shutil.copy2(archive_path, EVIDENCE_DIR / "archive-before-purge.log")

    tamper_process = MARKER + "_TAMPER"
    tamper_execution = str(uuid.uuid4())
    tamper_correlation = str(uuid.uuid4())
    tamper_log = RAW_ROOT / f"{tamper_execution}.log"
    tamper_log.write_text("conteudo-original\n", encoding="utf-8")
    enqueue_manual(tamper_process, tamper_log, tamper_execution, tamper_correlation, "tamper-e2e")
    tamper_log.write_text("conteudo-alterado-depois-do-ingresso\n", encoding="utf-8")
    run(
        "04-worker-tamper",
        [
            sys.executable,
            str(PIPELINE),
            "worker",
            "--once",
            "--batch-size",
            "1",
            "--lease-seconds",
            "30",
            "--retry-seconds",
            "3600",
            "--retention-days",
            "1",
            "--consumer",
            "e2e-worker-tamper",
        ],
    )
    state, attempts, _, archive_tamper = queue_state(tamper_execution)
    if state != "FALHA" or attempts != 1 or archive_tamper is not None or not tamper_log.exists():
        fail("controle negativo de adulteração não bloqueou o arquivamento")

    lease_process = MARKER + "_LEASE"
    lease_execution = str(uuid.uuid4())
    lease_correlation = str(uuid.uuid4())
    lease_log = RAW_ROOT / f"{lease_execution}.log"
    lease_log.write_text("lease-recovery\n", encoding="utf-8")
    enqueue_manual(lease_process, lease_log, lease_execution, lease_correlation, "lease-e2e")
    repository = SqlServerQueue(CONNECTION_STRING)
    first_lease = repository.reserve("e2e-lease-a", 1, 1)
    if len(first_lease) != 1 or first_lease[0].execucao_id != lease_execution or first_lease[0].tentativa != 1:
        fail("primeira reserva de lease não selecionou a execução esperada")
    time.sleep(2.0)
    second_lease = repository.reserve("e2e-lease-b", 1, 30)
    if len(second_lease) != 1 or second_lease[0].execucao_id != lease_execution or second_lease[0].tentativa != 2:
        fail("lease expirado não foi recuperado pelo segundo consumidor")
    repository.fail(second_lease[0].fila_id, "e2e-lease-b", "lease recovery validado", 3600)

    dlq_process = MARKER + "_DLQ"
    dlq_execution = str(uuid.uuid4())
    dlq_correlation = str(uuid.uuid4())
    dlq_log = RAW_ROOT / f"{dlq_execution}.log"
    dlq_log.write_text("arquivo-que-sera-removido\n", encoding="utf-8")
    enqueue_manual(dlq_process, dlq_log, dlq_execution, dlq_correlation, "dlq-e2e")
    dlq_log.unlink()
    for attempt in range(1, 4):
        run(
            f"05-worker-dlq-{attempt}",
            [
                sys.executable,
                str(PIPELINE),
                "worker",
                "--once",
                "--batch-size",
                "1",
                "--lease-seconds",
                "30",
                "--retry-seconds",
                "1",
                "--retention-days",
                "1",
                "--consumer",
                f"e2e-worker-dlq-{attempt}",
            ],
        )
        current_state, current_attempts, _, _ = queue_state(dlq_execution)
        expected_state = "DLQ" if attempt == 3 else "FALHA"
        if current_state != expected_state or current_attempts != attempt:
            fail(f"transição DLQ inválida na tentativa {attempt}: {current_state}/{current_attempts}")
        if attempt < 3:
            time.sleep(1.2)

    run(
        "06-worker-dlq-fourth-control",
        [
            sys.executable,
            str(PIPELINE),
            "worker",
            "--once",
            "--batch-size",
            "1",
            "--lease-seconds",
            "30",
            "--retry-seconds",
            "1",
            "--retention-days",
            "1",
            "--consumer",
            "e2e-worker-dlq-fourth",
        ],
    )
    state, attempts, _, _ = queue_state(dlq_execution)
    if state != "DLQ" or attempts != 3:
        fail("DLQ foi reservada novamente após terceira falha")

    write_snapshot("state-before-purge")
    execute(
        "UPDATE dbo.pentaho_log_fila SET retencao_ate=DATEADD(SECOND,-1,SYSUTCDATETIME()) WHERE execucao_id=? AND estado='CONCLUIDO'",
        (first_execution_id,),
    )
    run(
        "07-purge-main",
        [
            sys.executable,
            str(PIPELINE),
            "purge",
            "--once",
            "--batch-size",
            "1",
            "--lease-seconds",
            "30",
            "--retry-seconds",
            "3600",
            "--consumer",
            "e2e-purge-main",
        ],
    )
    final_state, _, _, _ = queue_state(first_execution_id)
    if final_state != "EXPURGADO" or archive_path.exists():
        fail("expurgo não consolidou SQL + ausência física do arquivo")

    run(
        "08-purge-idempotent-control",
        [
            sys.executable,
            str(PIPELINE),
            "purge",
            "--once",
            "--batch-size",
            "1",
            "--lease-seconds",
            "30",
            "--retry-seconds",
            "3600",
            "--consumer",
            "e2e-purge-repeat",
        ],
    )
    if queue_state(first_execution_id)[0] != "EXPURGADO":
        fail("repetição do expurgo alterou estado terminal")

    write_snapshot("state-final")
    summary = {
        "marker": MARKER,
        "main_execution_id": first_execution_id,
        "main_correlation_id": first_correlation_id,
        "main_final_state": "EXPURGADO",
        "tamper_execution_id": tamper_execution,
        "tamper_state": queue_state(tamper_execution)[0],
        "lease_execution_id": lease_execution,
        "lease_attempts": queue_state(lease_execution)[1],
        "dlq_execution_id": dlq_execution,
        "dlq_state": queue_state(dlq_execution)[0],
        "dlq_attempts": queue_state(dlq_execution)[1],
        "archive_sha256": sha256_file(EVIDENCE_DIR / "archive-before-purge.log"),
        "business_evidence_sha256": sha256_file(EVIDENCE_DIR / "business-evidence.csv"),
    }
    (EVIDENCE_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("E2E_PENTAHO_LOG_FULL_PASS")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
