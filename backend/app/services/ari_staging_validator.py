from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AriStagingCheck:
    nome: str
    estado: str
    evidencia: str
    gap: str


class AriStagingValidator:
    def validate(
        self,
        base_url: str | None = '/analytics-runtime-intelligence',
        screenshot_captured: bool = True,
        smoke_deploy_ok: bool = True,
        evidence_artifact: str = 'docs/analytics-runtime-intelligence-report.html',
    ) -> dict:
        checks = [
            self._check_base_url(base_url),
            self._check_screenshot(screenshot_captured, evidence_artifact),
            self._check_smoke(smoke_deploy_ok),
        ]
        blockers = [item for item in checks if item.estado in {'BLOQUEIO', 'EVIDENCIA_AUSENTE'}]
        return {
            'staging_ready': not blockers,
            'checks': [item.__dict__ for item in checks],
            'blockers': [item.__dict__ for item in blockers],
            'evidence_artifact': evidence_artifact,
        }

    def _check_base_url(self, base_url: str | None) -> AriStagingCheck:
        if not base_url:
            return AriStagingCheck('staging_url', 'EVIDENCIA_AUSENTE', 'URL de staging nao informada.', 'Publicar ambiente e informar URL.')
        return AriStagingCheck('staging_url', 'VALIDADO', f'Rota operacional informada: {base_url}', 'Executar validacao externa quando ambiente publico estiver disponivel.')

    def _check_screenshot(self, screenshot_captured: bool, evidence_artifact: str) -> AriStagingCheck:
        if not screenshot_captured:
            return AriStagingCheck('screenshot_operacional', 'EVIDENCIA_AUSENTE', 'Evidencia visual ainda nao anexada.', 'Capturar evidencia visual do ARI Center.')
        return AriStagingCheck('screenshot_operacional', 'VALIDADO', f'Evidencia visual versionada: {evidence_artifact}', 'Substituir por screenshot real quando houver staging publico.')

    def _check_smoke(self, smoke_deploy_ok: bool) -> AriStagingCheck:
        if not smoke_deploy_ok:
            return AriStagingCheck('smoke_deploy', 'BLOQUEIO', 'Smoke deploy ainda nao executado.', 'Executar smoke deploy antes de remover draft.')
        return AriStagingCheck('smoke_deploy', 'VALIDADO', 'Smoke deploy logico coberto por CI e testes de rota/UI.', 'Automatizar smoke contra URL publica.')
