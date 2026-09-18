# Cofre — despacho autorizado do Runtime Evidence Gate DEV

## Objetivo
Eliminar a dependência de sessão interativa do navegador para disparar o workflow oficial do Cofre em DEV, reutilizando o ReqSys Authorized Actions Gateway já governado.

## Requisitos
1. Aceitar somente o comando exato `/reqsys run cofre-runtime-evidence-dev`.
2. Manter a restrição ao issue canônico #1705 e ao ator `ericson-j-santos`.
3. Mapear somente para `cofre-runtime-evidence-gate.yml`.
4. Fixar `ref=main`, `environment=dev` e `timeout_seconds=20`.
5. Não permitir workflow, ref, ambiente ou inputs fornecidos pelo comentário.
6. Preservar `actions: write` e `contents: read`, sem ampliar permissões.
7. Registrar run id, run URL e SHA capturado sem ler segredos.
8. Manter `production_touched=false`.
9. STG/HML/PROD permanecem fora do escopo.

## Critérios de aceite
- teste positivo comprova rota exata para o Cofre DEV;
- teste negativo continua impedindo workflow arbitrário;
- YAML e testes direcionados passam;
- a PR permanece sem merge automático;
- após merge autorizado, o comando exato deve produzir novo `workflow_dispatch` no SHA então atual da main.
