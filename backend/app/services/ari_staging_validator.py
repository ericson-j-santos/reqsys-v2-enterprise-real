from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AriStagingCheck:
    nome: str
    estado: str
    evidencia: str
    gap: str


class AriStagingValidator:
    def validate(self, base_url: str | None = None, screenshot_captured: bool = False, smoke_deploy_ok: bool = False) -> dict:
        checks = [
            self._check_base_url(base_url),
            self._check_screenshot(screenshot_captured),
            self._check_smoke(smoke_deploy_ok),
        ]
        blockers = [item for item in checks if item.estado in {'BLOQUEIO', 'EVIDENCIA_AUSENTE'}]
        return {
            'staging_ready': not blockers,
            'checks': [item.__dict__ for item in checks],
            'blockers': [item.__dict__ for item in blockers],
        }

    def _check_base_url(self, base_url: str | None) -> AriStagingCheck:
        if not base_url:
            return AriStagingCheck('staging_url', 'EVIDENCIA_AUSENTE', 'URL de staging nao informada.', 'Publicar ambiente e informar URL.')
        return AriStagingCheck('staging_url', 'VALIDADO', f'URL informada: {base_url}', 'Executar validacao HTTP real.')

    def _check_screenshot(self, screenshot_captured: bool) -> AriStagingCheck:
        if not screenshot_captured:
            return AriStagingCheck('screenshot_operacional', 'EVIDENCIA_AUSENTE', 'Screenshot ainda nao anexado.', 'Capturar evidencia visual do ARI Center.')
        return AriStagingCheck('screenshot_operacional', 'VALIDADO', 'Screenshot operacional informado.', 'Versionar evidencia no PR.')

    def _check_smoke(self, smoke_deploy_ok: bool) -> AriStagingCheck:
        if not smoke_deploy_ok:
            return AriStagingCheck('smoke_deploy', 'BLOQUEIO', 'Smoke deploy ainda nao executado.', 'Executar smoke deploy antes de remover draft.')
        return AriStagingCheck('smoke_deploy', 'VALIDADO', 'Smoke deploy informado como aprovado.', 'Automatizar no CI/CD.')
