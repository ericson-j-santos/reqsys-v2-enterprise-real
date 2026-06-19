# PR19 Hardening Merge Race

Durante a continuidade do incremento, o PR #19 foi mesclado enquanto novos commits de hardening ainda estavam sendo aplicados na branch de origem.

## Decisão

Abrir um novo incremento a partir da `main` atual para reaplicar somente as alterações pendentes de hardening, evitando branch divergente e duplicidade de commits.

## Escopo pendente

- Health checks `/health/live` e `/health/ready`.
- Headers de segurança HTTP.
- Correlation ID.
- Gates de produção.
- Testes de hardening.
