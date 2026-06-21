# Registro de Riscos — Aba Estatísticas v1

| Risco | Probabilidade | Impacto | Mitigação | Status |
|---|---:|---:|---|---|
| Indicador local interpretado como real | Média | Alto | Exibir fonte, confiabilidade e pendências | Mitigado parcialmente |
| Dado externo sem auditoria | Média | Alto | Estado externo inicial `nao_medido` | Mitigado |
| Regressão de rota/menu | Baixa | Médio | Teste/build no CI | Pendente CI |
| Falha de responsividade | Média | Médio | Layout com grid responsivo | Pendente E2E |
| Estado avançado sem evidência | Baixa | Alto | Validador exige evidências | Mitigado inicialmente |
| Falha por dependência Vuetify | Baixa | Médio | Usa componentes já presentes na aplicação | Pendente build |

## Decisão

Não liberar para produção até CI verde, build validado e revisão dos dados reais internos.
