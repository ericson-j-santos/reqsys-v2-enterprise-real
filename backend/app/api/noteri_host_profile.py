from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.core.security import get_current_user, require_admin
from app.services import noteri_host_profile as profiles

router = APIRouter(prefix="/v1/noteri", tags=["Noteri Host Profile"])


class ProfileChangeInput(BaseModel):
    profile: str = Field(min_length=1, max_length=16)
    correlation_id: str = Field(min_length=8, max_length=128)


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, profiles.NoteriProfileUnavailable):
        return HTTPException(status_code=503, detail="Perfil do Noteri indisponível.")
    if isinstance(exc, profiles.NoteriProfileInvalid):
        return HTTPException(status_code=409, detail="Estado do perfil do Noteri inválido.")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=422, detail="Solicitação de perfil inválida.")
    return HTTPException(status_code=500, detail="Falha ao atualizar perfil do Noteri.")


@router.get("/profile")
def get_profile(_user: dict = Depends(get_current_user)):
    try:
        return ok(profiles.load_profile())
    except Exception as exc:
        raise _translate(exc) from exc


@router.post("/profile")
def change_profile(
    body: ProfileChangeInput,
    request: Request,
    _admin: dict = Depends(require_admin),
):
    header_correlation = (request.headers.get("X-Correlation-Id") or "").strip()
    if header_correlation and header_correlation != body.correlation_id.strip():
        raise HTTPException(status_code=409, detail="correlation_id_mismatch")
    try:
        return ok(profiles.set_profile(body.profile, body.correlation_id))
    except Exception as exc:
        raise _translate(exc) from exc
