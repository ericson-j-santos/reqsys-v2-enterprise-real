# Fabric HML Secret Bootstrap Temporário — Requisitos

## Objetivo

Provisionar de forma efêmera e governada o segredo `FABRIC_CLIENT_SECRET` no repositório `ericson-j-santos/painel-powerbi`, Environment `homologacao`, usando exclusivamente o runner self-hosted Noteri e sem expor o valor do segredo.

## Classificação

`gap_fix` operacional temporário. A PR não deve ser mergeada.

## Requisitos

1. Executar o bootstrap somente em pull request cuja branch seja exatamente `ops/fabric-hml-secret-bootstrap-20260921`.
2. Executar somente no runner allowlisted `[self-hosted, Windows, X64, noteri, reqsys-dev]`.
3. Preservar o job canônico de descoberta: em PR ele continua somente leitura; escrita das variáveis não sensíveis continua limitada ao `workflow_dispatch` na `main` com confirmação explícita.
4. Validar o tenant esperado e localizar exatamente uma App Registration `ReqSys ALM Pipeline`.
5. Localizar exatamente um workspace `ReqSys - Observabilidade`.
6. Criar nova credencial somente com `az ad app credential reset --append`; não remover credenciais existentes.
7. Enviar o valor de `FABRIC_CLIENT_SECRET` ao GitHub somente por stdin, nunca por argv, stdout ou arquivo.
8. Se a gravação do secret falhar ou o secret não for observado após a escrita, excluir a credencial recém-criada e registrar rollback.
9. Nunca imprimir ou persistir access token, client secret, Application ID ou Workspace ID em log ou artifact.
10. `FABRIC_HML_E2E_ENABLED=true` só é válido quando, na mesma execução, client credentials obtiver token, a API Fabric responder HTTP 200 e o workspace alvo estiver visível para a aplicação.
11. Quando um secret já existir e seu valor não puder ser relido para validação, manter `FABRIC_HML_E2E_ENABLED=false`, criar uma nova credencial com `--append`, validá-la antes de substituir o secret e somente então habilitar o E2E. Se a validação falhar, excluir apenas a credencial recém-criada e preservar o secret anterior.
12. Publicar somente evidência sanitizada.
13. Permanecer fail-closed diante de host, tenant, app, workspace ou validação ambígua.
14. Sem deploy, produção ou merge desta PR.

## Critérios de aceite

- Pre-PR Readiness verde no HEAD exato;
- contrato legado de descoberta permanece verde;
- branch sincronizada com a `main`;
- SDD do bootstrap presente e rastreável;
- nenhum segredo ou identificador privado exposto;
- nenhum estado E2E positivo sem validação real;
- teste de regressão comprova que a mera presença de um secret não habilita o E2E e que falha de validação executa rollback sem sobrescrever o secret anterior.
