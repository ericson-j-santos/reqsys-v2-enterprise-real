from __future__ import annotations

from app.domain.models.job_assincrono import JobAssincrono


class JobNaoEncontradoError(KeyError):
    """Erro de domínio para consulta de job inexistente."""


class JobRepositoryMemoria:
    def __init__(self) -> None:
        self._jobs: dict[str, JobAssincrono] = {}

    async def salvar(self, job: JobAssincrono) -> JobAssincrono:
        self._jobs[job.job_id] = job
        return job

    async def obter(self, job_id: str) -> JobAssincrono:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise JobNaoEncontradoError(job_id) from exc

    async def listar(self) -> list[JobAssincrono]:
        return list(self._jobs.values())

    async def metricas_por_status(self) -> dict[str, int]:
        metricas: dict[str, int] = {}
        for job in self._jobs.values():
            metricas[job.status.value] = metricas.get(job.status.value, 0) + 1
        return metricas
