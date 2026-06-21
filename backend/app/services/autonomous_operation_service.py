from app.models.operational_intelligence_models import DiagnosticoRuntime, StatusOperacional


class AutonomousOperationService:
    """Recomenda ação operacional segura com base no diagnóstico runtime."""

    def recomendar_acao(self, diagnostico: DiagnosticoRuntime) -> dict:
        if diagnostico.status == StatusOperacional.saudavel:
            return {
                "acao": "CONTINUAR_MONITORAMENTO",
                "autonomo": True,
                "exige_aprovacao": False,
                "justificativa": "Score saudável e sem riscos bloqueantes.",
            }

        if diagnostico.status == StatusOperacional.atencao:
            return {
                "acao": "REEXECUTAR_VALIDACOES",
                "autonomo": True,
                "exige_aprovacao": False,
                "justificativa": "Risco controlado permite revalidação automática.",
            }

        if diagnostico.status == StatusOperacional.degradado:
            return {
                "acao": "ABRIR_INCIDENTE_E_BLOQUEAR_PROMOCAO",
                "autonomo": True,
                "exige_aprovacao": True,
                "justificativa": "Estado degradado exige intervenção antes de merge/deploy.",
            }

        return {
            "acao": "BLOQUEAR_OPERACAO",
            "autonomo": True,
            "exige_aprovacao": True,
            "justificativa": "Estado bloqueado impede continuidade operacional segura.",
        }
