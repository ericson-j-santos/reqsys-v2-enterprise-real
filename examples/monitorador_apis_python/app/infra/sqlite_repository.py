import sqlite3
from pathlib import Path

from app.domain.models import ResultadoMonitoramento


class ResultadoRepositorySQLite:
    def __init__(self, caminho_banco: Path):
        self.caminho_banco = caminho_banco
        self.caminho_banco.parent.mkdir(parents=True, exist_ok=True)
        self._inicializar()

    def _conectar(self) -> sqlite3.Connection:
        return sqlite3.connect(self.caminho_banco)

    def _inicializar(self) -> None:
        with self._conectar() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resultados_monitoramento (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    url TEXT NOT NULL,
                    status_code INTEGER,
                    sucesso INTEGER NOT NULL,
                    tempo_resposta_ms REAL NOT NULL,
                    erro TEXT,
                    status_operacional TEXT NOT NULL,
                    consultado_em TEXT NOT NULL
                )
                """
            )

    def salvar(self, resultado: ResultadoMonitoramento) -> None:
        with self._conectar() as conn:
            conn.execute(
                """
                INSERT INTO resultados_monitoramento (
                    nome, url, status_code, sucesso, tempo_resposta_ms,
                    erro, status_operacional, consultado_em
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resultado.nome,
                    resultado.url,
                    resultado.status_code,
                    int(resultado.sucesso),
                    resultado.tempo_resposta_ms,
                    resultado.erro,
                    resultado.status_operacional,
                    resultado.consultado_em.isoformat(),
                ),
            )

    def listar_ultimos(self, limite: int = 50) -> list[dict]:
        with self._conectar() as conn:
            conn.row_factory = sqlite3.Row
            linhas = conn.execute(
                """
                SELECT *
                FROM resultados_monitoramento
                ORDER BY id DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()

        return [dict(linha) for linha in linhas]
