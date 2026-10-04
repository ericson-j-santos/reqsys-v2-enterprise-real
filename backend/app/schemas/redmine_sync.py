from pydantic import BaseModel


class RedmineSyncProcessarRequest(BaseModel):
    dry_run: bool = False
    lote_max: int | None = None
