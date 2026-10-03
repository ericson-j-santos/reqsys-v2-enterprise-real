# Fabric HML Noteri Discovery — Requisitos

## Objetivo

Recuperar, sem GUI/RDC e sem expor identificadores privados, a configuração não sensível necessária ao E2E Fabric HML do repositório `painel-powerbi`, usando o runner self-hosted Noteri como fallback governado enquanto o Desktop não está disponível.

## Classificação

`gap_fix`.

## Requisitos

1. Executar somente no runner allowlisted `[self-hosted, Windows, X64, noteri, reqsys-dev]`.
2. Em PR, operar em modo somente leitura por padrão; a única exceção é a branch exata `ops/fabric-hml-bootstrap-20260921`, criada como probe descartável e marcada para nunca ser mergeada, que pode aplicar somente as três Environment Variables não sensíveis no Environment `homologacao`.
3. Validar host, sessão Azure CLI no tenant esperado e acesso GitHub ao repositório alvo.
4. Localizar exatamente uma App Registration `ReqSys ALM Pipeline`.
5. Localizar exatamente um workspace `ReqSys - Observabilidade` pela API Fabric.
6. Nunca imprimir ou persistir access token, client secret, Application ID ou Workspace ID.
7. No modo manual em `main`, permitir somente gravação das três GitHub Environment Variables não sensíveis: `FABRIC_TENANT_ID`, `FABRIC_CLIENT_ID` e `FABRIC_WORKSPACE_ID`.
8. A exceção de PR deve exigir simultaneamente `github.event_name=pull_request` e `github.head_ref=ops/fabric-hml-bootstrap-20260921`; qualquer outra branch de PR permanece somente leitura.
9. Não criar, rotacionar ou gravar `FABRIC_CLIENT_SECRET`.
10. Publicar evidência sanitizada com estados, contagens e hashes apenas quando houver aplicação.
11. Permanecer fail-closed diante de host, tenant, app, workspace ou contexto de branch ambíguos.

## Critérios de aceite

- teste de contrato verde;
- Self-Hosted Runner Governance verde;
- probe no Noteri concluído no HEAD exato;
- nenhuma branch de PR diferente de `ops/fabric-hml-bootstrap-20260921` recebe permissão de escrita;
- nenhum identificador/segredo exposto em log ou artifact.
