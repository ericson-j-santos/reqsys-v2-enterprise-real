# Registro de Riscos — SQL Visual Explain Stack

| Risco | Impacto | Probabilidade | Mitigação |
|---|---:|---:|---|
| Parser heurístico falhar em SQL complexo | Médio | Alta | Evoluir para SQLGlot |
| Dependência nova quebrar CI | Médio | Média | Introduzir SQLGlot em PR separado |
| EXPLAIN em produção gerar carga | Alto | Média | Bloqueio por ambiente e aprovação |
| Relatório expor dados sensíveis | Alto | Média | Mascaramento e revisão |
| Documentação ficar desatualizada | Médio | Média | Geração automática futura em CI |
