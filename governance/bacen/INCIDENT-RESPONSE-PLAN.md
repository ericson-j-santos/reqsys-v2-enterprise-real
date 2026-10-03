# Plano de Resposta a Incidentes Cibernéticos

## Classificação

| Severidade | Critério | Resposta inicial |
|---|---|---|
| SEV-1 | indisponibilidade crítica, vazamento confirmado, comprometimento privilegiado | imediata |
| SEV-2 | impacto relevante ou risco elevado sem contenção completa | até 1 hora |
| SEV-3 | impacto limitado e controlado | até 4 horas |
| SEV-4 | evento informativo ou tentativa bloqueada | próximo ciclo operacional |

## Fluxo

1. Detectar e registrar correlation_id, horário, origem e sistemas afetados.
2. Classificar severidade e acionar `SECURITY` e `RUNTIME_OPERATOR`.
3. Preservar logs e evidências sem expor segredos ou dados pessoais.
4. Conter o incidente e impedir propagação.
5. Erradicar causa raiz e validar integridade.
6. Recuperar por procedimento controlado e executar smoke/readiness.
7. Avaliar comunicação executiva, contratual, aos titulares e ao regulador.
8. Emitir RCA, ações corretivas, responsáveis e prazos.
9. Atualizar controles, testes e runbooks.

## Evidência obrigatória

Cada incidente deve gerar registro imutável com severidade, impacto, decisões, linha do tempo, responsáveis, comunicação, evidências, RCA e validação pós-recuperação.

## Exercícios

Realizar exercício de mesa semestral e teste técnico anual. Incidentes relevantes exigem revisão extraordinária deste plano.
