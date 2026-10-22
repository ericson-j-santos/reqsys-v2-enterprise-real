# CI Governance Drift Guard — auditoria real de permissoes por job

## Problema
O run \`39709299873\`, SHA \`3e2c333c365f78b5bd6a69eaaa389611585e695d\`, falhou por procurar tokens textuais \`contents: write\` e \`pull-requests: write\` no workflow inteiro \`pr-ci-watch.yml\`. Esses escopos pertencem exclusivamente ao job \`structural-queue\`, nao a permissao global. O guard reportou um falso positivo estrutural.

## Requisitos e limites
1. Manter o workflow CI Governance Drift Guard existente, sem adicionar outro workflow ou afrouxar a politica de permissoes do ReqSys.
2. Interpretar o YAML (Loader BaseLoader, sem executavel dinamico, com PyYAML 6.0.3 fixado); auditar apenas declaracoes \`permissions\`, nunca comentarios ou strings contidas em scripts.
3. Falhar fechado em permissao global nao autorizada, \`write-all\`, permissao nao reconhecida, YAML invalido, mapa global omitido ou job com elevacao fora da allowlist.
4. Permissoes de escrita permitidas em \`pr-ci-watch.yml\` apenas para os jobs: \`structural-queue\` (contents, issues, pull-requests), \`manual-watch\` (issues), \`remediate-workflow-run\` (actions), \`sweep-open-prs\` (actions, issues). O \`watch-pr\` e outros jobs permanecem leitura.
5. Preservar a excecao existente de \`issues: write\` para PR Conflict Guard, documentando seu uso em comentarios. Nao autorizar \`contents: write\` na raiz.
6. Preservar todos os demais testes existentes de trigger e publicacao de artifacts e o status \`failed\` em drift verdadeiro; nenhuma alteracao aos scopes do PR CI Watch.
7. Executar os testes de permissao no proprio workflow \`ci-governance-drift-guard.yml\`, inclusive em PR com diff destes arquivos; confirmar novamente em \`main\` apos integracao antes de declarar correcao operacional.
8. Nenhum deploy, segredo, custo extra, compra, bypass, force-push ou publicacao produtiva.

## Critérios de aceite
- O parser rejeita campos YAML duplicados, inclusive `permissions` de root/job, e rejeita escopos de permissao desconhecidos mesmo somente leitura.
- A suite valida 6 workflows reais e detecta elevacao global/job indevida sem reduzir funcionalidade do PR CI Watch.
- O `READY_FOR_PR` no SHA final e o guard no CI PR realmente executam (sem skipped); a `main` pos-merge exige leitura independente.

## Testes
- Positivo: seis workflows criticos da versao atual analisados estruturalmente; permissoes por job esperadas aceitas.
- Negativos: root contents write, job nao autorizado, administration write, write-all global e de job, YAML invalido, falta do mapa global e troca indevida do Conflict Guard.
- Strings e comentarios com \`contents: write\` nao podem bloquear. Repeticao deterministica/idempotente.
- E2E no GitHub Actions: job Build drift report e artifact \`ci-governance-drift-report\` aprovados no SHA da PR e da main integrada.

## Rastreamento
Repo ReqSys, SHA base \`3e2c333c365f78b5bd6a69eaaa389611585e695d\`, workflow \`.github/workflows/ci-governance-drift-guard.yml\`, bug observado no run \`39709299873\`.
