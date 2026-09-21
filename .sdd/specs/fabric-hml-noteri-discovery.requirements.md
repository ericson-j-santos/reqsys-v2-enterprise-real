# Fabric HML Noteri Discovery — Requisitos

## Objetivo

Recuperar, sem GUI/RDC e sem expor identificadores privados, a configuração não sensível necessária ao E2E Fabric HML do repositório `painel-powerbi`, usando o runner self-hosted Noteri como fallback governado enquanto o Desktop não está disponível.

## Classificação

`gap_fix`.

## Requisitos

1. Executar somente no runner allowlisted `[self-hosted, Windows, X64, noteri, reqsys-dev]`.
2. Em PR, operar estritamente em modo somente leitura.
3. Validar host, sessão Azure CLI no tenant esperado e acesso GitHub ao repositório alvo.
4. Localizar exatamente uma App Registration `ReqSys ALM Pipeline`.
5. Localizar exatamente um workspace `ReqSys - Observabilidade` pela API Fabric.
6. Nunca imprimir ou persistir access token, client secret, Application ID ou Workspace ID.
7. No modo manual em `main`, permitir somente gravação das três GitHub Environment Variables não sensíveis: `FABRIC_TENANT_ID`, `FABRIC_CLIENT_ID` e `FABRIC_WORKSPACE_ID`.
8. Não criar, rotacionar ou gravar `FABRIC_CLIENT_SECRET`.
9. Publicar evidência sanitizada com estados, contagens e hashes apenas quando houver aplicação.
10. Permanecer fail-closed diante de host, tenant, app ou workspace ambíguos.

## Critério de aceite

- teste de contrato verde;
- Self-Hosted Runner Governance verde;
- probe no Noteri concluído no HEAD exato;
- nenhum identificador/segredo exposto em log ou artifact.
