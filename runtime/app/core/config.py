from functools import lru_cache
from pydantic import BaseModel
import os


class RuntimeSettings(BaseModel):
    service_name: str = "reqsys-runtime"
    schema_version: str = "0.5.0"
    enable_async_worker: bool = False
    max_tentativas: int = 3


@lru_cache
def get_settings() -> RuntimeSettings:
    return RuntimeSettings(
        enable_async_worker=os.getenv("ENABLE_ASYNC_WORKER", "false").lower() == "true",
        max_tentativas=int(os.getenv("ASYNC_JOB_MAX_TENTATIVAS", "3")),
    )
