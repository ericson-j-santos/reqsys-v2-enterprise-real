import hashlib
import json
from time import time_ns
from urllib import request
from urllib.error import HTTPError, URLError

from app.core.secrets import get_secret
from app.services.github_version_checker import verificar_versao_github

_REQSYS_VERSION = "2.7.0"


# ---------------------------------------------------------------------------
# Geração de conteúdo Wiki
# ---------------------------------------------------------------------------

def gerar_conteudo_wiki_requisito(requisito: dict) -> str:
    codigo = requisito.get("codigo", "SEM-CODIGO")
    titulo = requisito.get("titulo", "Sem título")
    descricao = requisito.get("descricao", "")
    status = requisito.get("status", "recebido")
    area = requisito.get("area", "-")
    sistema = requisito.get("sistema", "-")
    solicitante = requisito.get("solicitante", "-")
    urgencia = requisito.get("urgencia", "media")
    impacto = "Sim" if requisito.get("impacto_regulatorio") else "Não"
    criado_em = str(requisito.get("criado_em", "-"))

    return (
        f"# {codigo} — {titulo}\n\n"
        f"| Campo | Valor |\n"
        f"|---|---|\n"
        f"| **Status** | {status} |\n"
        f"| **Área** | {area} |\n"
        f"| **Sistema** | {sistema} |\n"
        f"| **Solicitante** | {solicitante} |\n"
        f"| **Urgência** | {urgencia} |\n"
        f"| **Impacto Regulatório** | {impacto} |\n"
        f"| **Criado em** | {criado_em} |\n\n"
        f"## Descrição\n\n"
        f"{descricao}\n\n"
        f"---\n\n"
        f"*Publicado automaticamente pelo ReqSys Enterprise v{_REQSYS_VERSION}*\n"
    )


def _hash_conteudo(conteudo: str) -> str:
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Verificação de versão no GitHub
# ---------------------------------------------------------------------------

def _checar_github(codigo: str, hash_reqsys: str) -> dict | None:
    repo = (get_secret("GITHUB_DOCS_REPO", "") or "").strip()
    if not repo:
        return None

    base_path = (get_secret("GITHUB_DOCS_BASE_PATH", "docs/requisitos") or "docs/requisitos").strip()
    arquivo = f"{base_path}/{codigo}.md"
    return verificar_versao_github(repo, arquivo, hash_reqsys)


# ---------------------------------------------------------------------------
# Chamada ao Redmine Wiki Sync service
# ---------------------------------------------------------------------------

def _chamar_wiki_sync(wiki_page_title: str, conteudo: str, correlation_id: str) -> dict:
    base_url = (get_secret("WIKI_SYNC_BASE_URL", "") or "").strip().rstrip("/")
    token = (get_secret("WIKI_SYNC_TOKEN", "") or "").strip()

    if not base_url:
        return {
            "publicado": False,
            "correlation_id": correlation_id,
            "wiki_page_title": wiki_page_title,
            "status_publicacao": "erro",
            "mensagem": (
                "WIKI_SYNC_BASE_URL não configurado. "
                "Defina a URL do serviço Redmine Wiki Sync no .env."
            ),
        }

    payload = json.dumps({
        "wikiPageTitle": wiki_page_title,
        "content": conteudo,
        "sourceSystem": "reqsys",
        "sourceVersion": _REQSYS_VERSION,
        "forceUpdate": False,
    }).encode("utf-8")

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": f"reqsys-wiki-publisher/{_REQSYS_VERSION}",
        "X-Correlation-ID": correlation_id,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = request.Request(
            url=f"{base_url}/v1/sync/wiki",
            data=payload,
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            novo_correlation = body.get("data", {}).get("correlationId", correlation_id)
            return {
                "publicado": True,
                "correlation_id": novo_correlation,
                "wiki_page_title": wiki_page_title,
                "status_publicacao": "publicado",
                "mensagem": "Requisito enfileirado no Redmine Wiki Sync com sucesso.",
            }
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:400]
        return {
            "publicado": False,
            "correlation_id": correlation_id,
            "wiki_page_title": wiki_page_title,
            "status_publicacao": "erro",
            "mensagem": f"Erro HTTP {exc.code} ao chamar Wiki Sync: {detail}",
        }
    except (URLError, Exception) as exc:
        return {
            "publicado": False,
            "correlation_id": correlation_id,
            "wiki_page_title": wiki_page_title,
            "status_publicacao": "erro",
            "mensagem": f"Falha de conexão ao Wiki Sync: {exc}",
        }


# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------

def publicar_requisito_no_wiki(
    requisito: dict,
    correlation_id: str,
    forcar_atualizacao: bool = False,
) -> dict:
    """
    Fluxo completo:
      1. Gera conteúdo Markdown do requisito
      2. Verifica versão no GitHub (se GITHUB_DOCS_REPO configurado)
      3. Decide se publica ou bloqueia
      4. Chama o Redmine Wiki Sync service
    """
    codigo = requisito.get("codigo", "REQ-000")
    wiki_page_title = f"Requisitos/{codigo}"
    conteudo = gerar_conteudo_wiki_requisito(requisito)
    hash_reqsys = _hash_conteudo(conteudo)

    # — Passo 2: verificar GitHub
    github_status = _checar_github(codigo, hash_reqsys)

    if github_status is not None:
        status_gh = github_status["status"]

        if status_gh == "sincronizado" and not forcar_atualizacao:
            return {
                "publicado": False,
                "correlation_id": correlation_id,
                "wiki_page_title": wiki_page_title,
                "status_publicacao": "ignorado_conteudo_identico",
                "github_version": github_status,
                "mensagem": "Conteúdo já sincronizado com o GitHub. Publicação ignorada.",
            }

        if status_gh == "divergente" and not forcar_atualizacao:
            return {
                "publicado": False,
                "correlation_id": correlation_id,
                "wiki_page_title": wiki_page_title,
                "status_publicacao": "bloqueado_divergencia_github",
                "github_version": github_status,
                "mensagem": (
                    "O GitHub possui uma versão diferente deste arquivo. "
                    "Revise o conteúdo e use forcar_atualizacao=true para publicar."
                ),
            }

    # — Passo 3: publicar via Wiki Sync
    resultado = _chamar_wiki_sync(wiki_page_title, conteudo, correlation_id)
    resultado["github_version"] = github_status
    return resultado


def consultar_status_wiki(requisito: dict) -> dict:
    """Consulta somente o status de sincronização sem publicar."""
    codigo = requisito.get("codigo", "REQ-000")
    conteudo = gerar_conteudo_wiki_requisito(requisito)
    hash_reqsys = _hash_conteudo(conteudo)

    repo = (get_secret("GITHUB_DOCS_REPO", "") or "").strip()
    if not repo:
        return {
            "wiki_page_title": f"Requisitos/{codigo}",
            "github_version": {
                "status": "verificacao_desabilitada",
                "arquivo_github": None,
                "hash_github": None,
                "hash_reqsys": hash_reqsys,
                "mensagem": "GITHUB_DOCS_REPO não configurado.",
            },
        }

    github_status = _checar_github(codigo, hash_reqsys)
    return {
        "wiki_page_title": f"Requisitos/{codigo}",
        "github_version": github_status,
    }
