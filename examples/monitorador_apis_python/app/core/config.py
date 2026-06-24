from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApiAlvo:
    nome: str
    url: str
    timeout_segundos: float = 5.0


@dataclass(frozen=True)
class Configuracao:
    banco_sqlite: Path = Path("data/monitoramento.db")
    diretorio_logs: Path = Path("logs")
    diretorio_relatorios: Path = Path("reports")
    tentativas_retry: int = 3
    cache_ttl_segundos: int = 30


APIS_PADRAO = [
    ApiAlvo(nome="httpbin_status_200", url="https://httpbin.org/status/200"),
    ApiAlvo(nome="httpbin_delay", url="https://httpbin.org/delay/1"),
    ApiAlvo(nome="jsonplaceholder", url="https://jsonplaceholder.typicode.com/posts/1"),
]
