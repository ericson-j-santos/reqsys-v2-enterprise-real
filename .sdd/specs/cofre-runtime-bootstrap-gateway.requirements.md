# Authorized Actions Gateway — bootstrap Cofre Runtime

## Objetivo
Permitir que o chat acione o bootstrap S2S do Cofre por um comando fixo e governado, sem workflow ou input arbitrário.

## Requisitos
1. Aceitar somente o comando exato `/reqsys run cofre-runtime-service-token-bootstrap`.
2. Mapear somente para `pc24x7-teams-token-bootstrap.yml`.
3. Forçar `mode=cofre-runtime`.
4. Preservar o comando Teams existente com `mode=teams`.
5. O dispatcher deve recusar qualquer outro modo para esse workflow.
6. Nenhum segredo é aceito como input do gateway.

## Critérios de aceite
- Comando Cofre aparece na allowlist externa e no case interno.
- Target é fixo.
- Mode é fixo e validado novamente no dispatcher.
- Teams continua permitido separadamente.
- Não há workflow/input arbitrário.
