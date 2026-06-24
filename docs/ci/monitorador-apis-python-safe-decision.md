# Decisão segura — Correção CI Monitorador APIs Python

## Decisão

Corrigir a falha do workflow por aumento de cobertura de testes, preservando o gate de 85%.

## Justificativa

Reduzir cobertura resolveria o sintoma, mas reduziria a maturidade técnica. A alternativa escolhida mantém o padrão de qualidade e melhora a validação real dos endpoints.

## Status alvo

- PR corretivo aberto.
- Workflow `Testes Monitorador APIs Python` verde.
- Merge somente após evidência do CI.
