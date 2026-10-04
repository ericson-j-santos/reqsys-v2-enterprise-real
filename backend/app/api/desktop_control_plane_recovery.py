from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.core.security import require_admin
from app.services import desktop_control_plane_recovery as recovery

router = APIRouter(
    prefix="/api/internal/desktop-control-plane",
    tags=["Desktop Control Plane Recovery"],
)


class DesktopControlPlaneRecoveryInput(BaseModel):
    correlation_id: str = Field(min_length=8, max_length=160)


@router.post("/recover", status_code=status.HTTP_202_ACCEPTED)
def recover_desktop_control_plane(
    body: DesktopControlPlaneRecoveryInput,
    request: Request,
    _admin: dict = Depends(require_admin),
):
    header_correlation = (request.headers.get("X-Correlation-Id") or "").strip()
    if header_correlation and header_correlation != body.correlation_id.strip():
        raise HTTPException(status_code=409, detail="correlation_id_mismatch")
    try:
        return ok(recovery.dispatch_control_plane_recovery(body.correlation_id))
    except recovery.DesktopRecoveryDispatchError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.code) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="desktop_control_plane_recovery_failed",
        ) from exc
