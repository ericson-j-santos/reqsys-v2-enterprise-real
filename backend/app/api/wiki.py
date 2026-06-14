from time import time_ns

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.models.requisito import Requisito
from app.schemas.requisito import RequisitoOut
from app.schemas.wiki import PublicarWikiRequest
from app.services.auditoria import registrar_evento
from app.services.wiki_publisher import (
    consultar_status_wiki,
    publicar_requisito_no_wiki,
)

router = APIRouter(prefix="/v1/wiki", tags=["Wiki"])


@router.post(
    "/requisitos/{requisito_id}/publicar",
    summary="Publica um requisito na Wiki do Redmine",
)
def publicar_requisito(
    requisito_id: int,
    payload: PublicarWikiRequest,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    req = db.query(Requisito).filter(Requisito.id == requisito_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requisito não encontrado.")

    correlation_id = x_correlation_id or payload.correlation_id or f"wiki-{str(time_ns())[-9:]}"
    requisito_dict = RequisitoOut.model_validate(req).model_dump()

    resultado = publicar_requisito_no_wiki(
        requisito_dict,
        correlation_id,
        payload.forcar_atualizacao,
    )

    registrar_evento(
        db,
        correlation_id,
        requisito_dict.get("solicitante", "sistema"),
        "WIKI_PUBLICAR" if resultado["publicado"] else f"WIKI_{resultado['status_publicacao'].upper()}",
        "requisito",
        requisito_id,
        f'{{"wiki_page": "{resultado["wiki_page_title"]}", "status": "{resultado["status_publicacao"]}"}}',
    )

    return ok(resultado, correlation_id)


@router.get(
    "/requisitos/{requisito_id}/status",
    summary="Consulta o status de sincronizacao de um requisito com GitHub e Wiki",
)
def status_requisito(
    requisito_id: int,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    req = db.query(Requisito).filter(Requisito.id == requisito_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requisito não encontrado.")

    requisito_dict = RequisitoOut.model_validate(req).model_dump()
    status_result = consultar_status_wiki(requisito_dict)

    return ok(
        {
            "requisito_id": requisito_id,
            "codigo": requisito_dict.get("codigo"),
            "wiki_page_title": status_result["wiki_page_title"],
            "github_version": status_result["github_version"],
            "mensagem": status_result.get("github_version", {}).get("mensagem", ""),
        },
        x_correlation_id,
    )


@router.post(
    "/requisitos/publicar-lote",
    summary="Publica múltiplos requisitos na Wiki em lote",
)
def publicar_lote(
    payload: PublicarWikiRequest,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    requisitos = db.query(Requisito).all()
    correlation_id = x_correlation_id or f"wiki-lote-{str(time_ns())[-9:]}"

    resultados = []
    for req in requisitos:
        requisito_dict = RequisitoOut.model_validate(req).model_dump()
        resultado = publicar_requisito_no_wiki(
            requisito_dict,
            f"{correlation_id}-{req.id}",
            payload.forcar_atualizacao,
        )
        resultados.append({
            "requisito_id": req.id,
            "codigo": requisito_dict.get("codigo"),
            **resultado,
        })

    publicados = sum(1 for r in resultados if r["publicado"])
    ignorados = sum(1 for r in resultados if r["status_publicacao"] == "ignorado_conteudo_identico")
    erros = sum(1 for r in resultados if r["status_publicacao"] == "erro")

    return ok(
        {
            "total": len(resultados),
            "publicados": publicados,
            "ignorados": ignorados,
            "erros": erros,
            "itens": resultados,
        },
        correlation_id,
    )
