# Incidente pós-merge — Monitorador de APIs Python

## Origem

PR #161 mergeado com falha posterior no workflow específico do monitorador.

## Sintoma

- Workflow: `Testes Monitorador APIs Python`
- Run: `28068262472`
- Job: `83097214550`
- Step: `Executar testes com cobertura mínima`
- Conclusão: `failure`

## Contenção

Criado PR corretivo dedicado, sem novo incremento funcional, focado apenas em estabilizar o CI.

## Prevenção

- Expandir testes antes de elevar escopo de endpoints.
- Manter endpoints com chamadas externas mockadas no CI.
- Preservar limiar de cobertura até evidência em contrário.
