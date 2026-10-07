# GitHub Actions — migração repository-wide para Node.js 24

## Objetivo

Eliminar dos workflows versionados todas as referências conhecidas a Actions baseadas em Node.js 20, preservando pinagem imutável, semântica dos jobs e governança de CI.

## Escopo

- Actions oficiais GitHub: cache, checkout, Pages, App Token, artifacts, github-script, setup-node e setup-python.
- `azure/login`.
- Actions Docker: build-push, login e setup-buildx.
- Slack GitHub Action.
- Composite Actions locais e testes de contrato que verificam os SHAs imutáveis.

## Requisitos

1. Substituir somente referências de Action e seus comentários de versão, sem alterar triggers, permissões, secrets, environments, comandos ou lógica dos jobs.
2. Fixar todas as releases aprovadas pelo SHA completo do respectivo tag.
3. Usar somente releases cujo `action.yml` oficial declare Node.js 24 ou, no caso de composite actions, componha versões atuais compatíveis.
4. Remover os 17 SHAs e as referências mutáveis Node.js 20 inventariadas, exceto as três referências existentes em cada um dos workflows STG protegidos `stg-blocking-policy-authorization.yml` e `stg-enforcement-approval.yml`; esses dois arquivos ficam explicitamente fora deste lote porque qualquer alteração neles exige aprovação humana STG vinculada ao HEAD.
5. Atualizar testes de contrato que verificam as referências imutáveis.
6. Incluir teste repository-wide que bloqueie a reintrodução dos SHAs removidos.
7. Validar todos os YAML, imutabilidade das Actions, contratos de regressão e testes afetados antes da PR.
8. Não executar deploy ou alterar runtime como parte desta migração.\n9. Tratar os dois workflows STG protegidos como exceção temporária fechada: somente `actions/checkout@v4`, `actions/setup-python@v5` e `actions/upload-artifact@v4` podem permanecer neles, e a migração deve ocorrer em PR separado submetido ao próprio `STG Blocking Policy Authorization`.

## Critérios de aceite

- Nenhum SHA Node.js 20 inventariado aparece em `.github/workflows` ou `.github/actions`; tags mutáveis só podem permanecer nas duas exceções STG protegidas e exatamente no conjunto documentado.
- As 19 famílias de Actions migradas aparecem fixadas pelos SHAs Node.js 24 aprovados.
- `tests/test_github_actions_node24_migration.py` aprovado.
- Todos os testes que referenciam as Actions migradas aprovados.
- `scripts/validate_action_immutability.py` e `scripts/validate_workflow_regression_contracts.py` aprovados.
- Todos os workflows continuam sendo YAML válido.
