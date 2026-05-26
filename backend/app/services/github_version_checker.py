import hashlib
import json
from base64 import b64decode
from urllib import request
from urllib.error import HTTPError, URLError

from app.core.secrets import get_secret


def _hash_conteudo(conteudo: str) -> str:
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


def verificar_versao_github(repo: str, file_path: str, hash_reqsys: str) -> dict:
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
        with request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
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
    except (URLError, Exception) as exc:
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
