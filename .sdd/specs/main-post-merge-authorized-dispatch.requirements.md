# Dispatch governado da validação pós-merge no SHA corrente da main

## Objetivo

Permitir que o owner dispare, pelo ReqSys Authorized Actions Gateway, a validação
`Main Post-Merge Validation` imediatamente após um merge governado, sem depender
do cron e sem usar shell remoto como atalho.

## Requisitos

1. O comando autorizado deve ser exatamente `/reqsys run main-post-merge-current-main`.
2. O comando só pode ser aceito na issue canônica #1705 e quando criado pelo owner já permitido pelo gateway.
3. O target deve ser fixo: `main-post-merge-validation.yml`.
4. O gateway deve capturar o SHA corrente de `main` antes do dispatch.
5. O workflow deve ser disparado com `--ref main` e `commit_sha=$EXPECTED_SHA`.
6. O modo deve ser fixo como `exact-main`; valores arbitrários não são aceitos.
7. A validação existente do gateway deve comprovar `run_id`, URL, evento `workflow_dispatch` e `headSha` iguais ao dispatch.
8. O comando não pode aceitar workflow, branch, SHA ou input arbitrário fornecido pelo comentário.
9. O incremento não autoriza deploy, promoção, produção, secrets ou alteração administrativa.
10. O alvo é GitHub-hosted; não deve ser classificado como workflow que exige pickup self-hosted.

## Critérios de aceite

- Pre-PR Readiness verde no HEAD exato e `behind_by=0`;
- testes de contrato do gateway verdes;
- SDD, security changed-diff e workflow regression contracts verdes;
- após merge, o comando produz run do `Main Post-Merge Validation` no SHA exato da `main`;
- o run pós-merge executa o security delta strict e publica a evidência correspondente.
