from app.models.operational_intelligence_models import (
    DiagnosticoRuntime,
    SinalRuntime,
    StatusOperacional,
)


class RuntimeIntelligenceService:
    """Calcula score operacional determinístico e explicável."""

    def diagnosticar(self, sinais: list[SinalRuntime]) -> DiagnosticoRuntime:
        if not sinais:
            return DiagnosticoRuntime(
                status=StatusOperacional.bloqueado,
                score=0,
                riscos=["Nenhum sinal operacional recebido."],
                recomendacoes=["Bloquear promoção e validar pipeline de telemetria."],
            )

        score = 100
        riscos: list[str] = []
        recomendacoes: list[str] = []

        for sinal in sinais:
            if not sinal.sucesso:
                score -= 25 if sinal.criticidade == "alta" else 15
                riscos.append(f"{sinal.nome}: falha operacional detectada.")
                recomendacoes.append(f"{sinal.nome}: executar retry controlado e registrar auditoria.")

            if sinal.latencia_ms > 5000:
                score -= 10
                riscos.append(f"{sinal.nome}: latência acima de 5s.")
                recomendacoes.append(f"{sinal.nome}: revisar timeout e circuit breaker.")

            if sinal.retries > 2:
                score -= 10
                riscos.append(f"{sinal.nome}: excesso de retries.")
                recomendacoes.append(f"{sinal.nome}: avaliar dead-letter e causa raiz.")

            if sinal.falhas_consecutivas >= 3:
                score -= 30
                riscos.append(f"{sinal.nome}: falhas consecutivas críticas.")
                recomendacoes.append(f"{sinal.nome}: abrir incidente e bloquear avanço automático.")

        score = max(0, min(100, score))
        status = (
            StatusOperacional.saudavel
            if score >= 90
            else StatusOperacional.atencao
            if score >= 70
            else StatusOperacional.degradado
            if score >= 40
            else StatusOperacional.bloqueado
        )

        if not recomendacoes:
            recomendacoes.append("Manter monitoramento e preservar evidências operacionais.")

        return DiagnosticoRuntime(status=status, score=score, riscos=riscos, recomendacoes=recomendacoes)
