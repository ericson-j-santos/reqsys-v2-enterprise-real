from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class AriStagingCheck:
    nome: str
    estado: str
    evidencia: str
    gap: str


class AriStagingValidator:
    """Valida somente evidências explicitamente fornecidas; defaults falham fechados."""

    def validate(
        self,
        base_url: str | None = None,
        screenshot_captured: bool = False,
        smoke_deploy_ok: bool = False,
        evidence_artifact: str | None = None,
    ) -> dict:
        checks = [
            self._check_base_url(base_url),
            self._check_screenshot(screenshot_captured, evidence_artifact),
            self._check_smoke(smoke_deploy_ok),
        ]
        blockers = [item for item in checks if item.estado != 'VALIDADO']
        return {
            'staging_ready': not blockers,
            'checks': [asdict(item) for item in checks],
            'blockers': [asdict(item) for item in blockers],
            'evidence_artifact': evidence_artifact,
        }

    def _check_base_url(self, base_url: str | None) -> AriStagingCheck:
        parsed = urlparse(base_url or '')
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            return AriStagingCheck(
                'staging_url',
                'EVIDENCIA_AUSENTE',
                'URL externa de staging não comprovada.',
                'Informar URL HTTP(S) válida do ambiente evidenciado.',
            )
        return AriStagingCheck('staging_url', 'VALIDADO', f'URL externa informada: {parsed.scheme}://{parsed.netloc}', 'Revalidar no mesmo ciclo de evidência.')

    def _check_screenshot(self, screenshot_captured: bool, evidence_artifact: str | None) -> AriStagingCheck:
        if not screenshot_captured or not evidence_artifact:
            return AriStagingCheck(
                'visual_evidence',
                'EVIDENCIA_AUSENTE',
                'Readback visual atual não foi fornecido.',
                'Capturar evidência visual vinculada à execução atual.',
            )
        return AriStagingCheck('visual_evidence', 'VALIDADO', f'Evidência visual registrada em {evidence_artifact}.', 'Preservar vínculo com a execução.')

    def _check_smoke(self, smoke_deploy_ok: bool) -> AriStagingCheck:
        if not smoke_deploy_ok:
            return AriStagingCheck(
                'staging_smoke',
                'EVIDENCIA_AUSENTE',
                'Smoke externo não comprovado.',
                'Executar smoke governado no ambiente alvo.',
            )
        return AriStagingCheck('staging_smoke', 'VALIDADO', 'Smoke externo informado como aprovado.', 'Preservar artifact/readback do smoke.')
