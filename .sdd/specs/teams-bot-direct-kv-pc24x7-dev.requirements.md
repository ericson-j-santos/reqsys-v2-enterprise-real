# Teams Bot direto via Key Vault no PC24x7 DEV

## Objetivo

Ativar o runtime Teams Bot em DEV no PC24x7 reutilizando a credencial existente do Azure Key Vault localmente, sem relay público efêmero, sem ampliar permissões e preservando o provedor Ollama já disponível no Desktop.

## Critérios de aceite

1. A execução é limitada ao ambiente DEV e exige confirmação explícita.
2. O runtime alvo deve corresponder exatamente ao SHA informado.
3. A credencial existente deve ser lida do Key Vault somente no processo local autorizado e nunca aparecer em log ou evidência.
4. A credencial deve ser removida do ambiente filho antes do E2E.
5. O override deve configurar o Bot e preservar o endpoint Ollama local do PC24x7.
6. O E2E deve exigir readiness `ready=true`, token efêmero revogado, replay idempotente e entrega via canal `bot`.
7. Evidência final deve registrar `secret_value_exposed=false` e `production_touched=false`.
8. TEST/HML/STG/PROD permanecem fora do escopo.

## Rastreabilidade

- #1532 — ativação da Central de Conversas IA/Teams em DEV.
- #993 — pendências operacionais ReqSys.
