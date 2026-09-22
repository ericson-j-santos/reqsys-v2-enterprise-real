from typing import Literal

from pydantic import BaseModel


class PublicarWikiRequest(BaseModel):
    forcar_atualizacao: bool = False
    correlation_id: str | None = None


class GitHubVersionStatus(BaseModel):
    status: Literal[
        "sincronizado",
        "divergente",
        "nao_encontrado",
        "verificacao_desabilitada",
        "erro",
    ]
    arquivo_github: str | None = None
    hash_github: str | None = None
    hash_reqsys: str
    mensagem: str


class PublicarWikiResult(BaseModel):
    publicado: bool
    correlation_id: str
    wiki_page_title: str
    status_publicacao: Literal[
        "publicado",
        "ignorado_conteudo_identico",
        "bloqueado_divergencia_github",
        "erro",
    ]
    github_version: GitHubVersionStatus | None = None
    mensagem: str


class WikiStatusResult(BaseModel):
    requisito_id: int
    codigo: str
    wiki_page_title: str
    github_version: GitHubVersionStatus | None = None
    mensagem: str
