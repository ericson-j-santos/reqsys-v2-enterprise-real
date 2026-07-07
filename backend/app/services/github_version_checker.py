import hashlib
import json
import time
from base64 import b64decode
from urllib import request
from urllib.error import HTTPError, URLError

from app.core.resilience import CircuitBreaker, HTTPErrorNaoRetentavel, call_with_retry
from app.core.secrets import get_secret

GITHUB_VERSION_MAX_RETRIES = 3
GITHUB_VERSION_RETRY_BACKOFF_SECONDS = 0.5
GITHUB_VERSION_CIRCUIT_FAILURE_THRESHOLD = 3
GITHUB_VERSION_CIRCUIT_COOLDOWN_SECONDS = 60

_circuit = CircuitBreaker(
    name='github_version_checker',
    failure_threshold=GITHUB_VERSION_CIRCUIT_FAILURE_THRESHOLD,
    cooldown_seconds=GITHUB_VERSION_CIRCUIT_COOLDOWN_SECONDS,
)


def reset_circuit_breaker() -> None:
    """Reseta o estado do circuit breaker (uso em testes)."""
    _circuit.reset()


def _hash_conteudo(conteudo: str) -> str:
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


def _do_fetch(req: request.Request) -> dict:
    try:
        with request.urlopen(req, timeout=10) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raise HTTPErrorNaoRetentavel(exc) from exc


def verificar_versao_github(
    repo: str,
    file_path: str,
    hash_reqsys: str,
    *,
    sleep=time.sleep,
    max_retries: int = GITHUB_VERSION_MAX_RETRIES,
) -> dict:
    """
    Verifica no GitHub se já existe uma versão do arquivo e compara com o
    conteúdo que o ReqSys quer publicar.

    Retorna dict com:
        status: "sincronizado" | "divergente" | "nao_encontrado" | "erro"
        arquivo_github: caminho verificado
        hash_github: hash SHA256 do conteúdo no GitHub (se encontrado)
        hash_reqsys: hash SHA256 do conteúdo do ReqSys
        conteudo_github: texto decodificado do GitHub (se divergente)
        mensagem: descrição legível
    """
    token = (get_secret("GITHUB_TOKEN", "") or "").strip()
    headers: dict[str, str] = {
        "User-Agent": "reqsys-wiki-publisher/2.7.0",
        "Accept": "application/vnd.github.v3+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"

    try:
        req = request.Request(url=url, headers=headers, method="GET")
        data = call_with_retry(
            lambda: _do_fetch(req),
            max_retries=max_retries,
            backoff_seconds=GITHUB_VERSION_RETRY_BACKOFF_SECONDS,
            retry_on=(URLError,),
            sleep=sleep,
            circuit=_circuit,
        )
    except HTTPErrorNaoRetentavel as wrapper:
        exc = wrapper.original
        if exc.code == 404:
            return {
                "status": "nao_encontrado",
                "arquivo_github": file_path,
                "hash_github": None,
                "hash_reqsys": hash_reqsys,
                "conteudo_github": None,
                "mensagem": f"Arquivo '{file_path}' não encontrado no GitHub. Será criado na Wiki.",
            }
        return {
            "status": "erro",
            "arquivo_github": file_path,
            "hash_github": None,
            "hash_reqsys": hash_reqsys,
            "conteudo_github": None,
            "mensagem": f"Erro HTTP {exc.code} ao verificar versão no GitHub.",
        }
    except Exception as exc:
        return {
            "status": "erro",
            "arquivo_github": file_path,
            "hash_github": None,
            "hash_reqsys": hash_reqsys,
            "conteudo_github": None,
            "mensagem": f"Falha ao conectar ao GitHub: {exc}",
        }

    conteudo_github = b64decode(data.get("content", "")).decode("utf-8")
    hash_github = _hash_conteudo(conteudo_github)

    if hash_github == hash_reqsys:
        return {
            "status": "sincronizado",
            "arquivo_github": file_path,
            "hash_github": hash_github,
            "hash_reqsys": hash_reqsys,
            "conteudo_github": None,
            "mensagem": "Conteúdo idêntico ao GitHub. Nenhuma atualização necessária.",
        }

    return {
        "status": "divergente",
        "arquivo_github": file_path,
        "hash_github": hash_github,
        "hash_reqsys": hash_reqsys,
        "conteudo_github": conteudo_github,
        "mensagem": (
            f"O arquivo '{file_path}' no GitHub diverge do ReqSys. "
            "Use forcar_atualizacao=true para publicar mesmo assim."
        ),
    }
