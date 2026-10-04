# Requisitos — PR Evidence Gate fail-closed

## Objetivo

Impedir falso verde no merge quando checks governados não executarem efetivamente no HEAD atual da pull request.

## Requisitos funcionais

1. O PR Evidence Gate deve avaliar evidência vinculada ao `head_sha` atual da PR.
2. Para cada workflow obrigatório/governado, somente a execução mais recente no mesmo HEAD pode determinar o estado do gate.
3. Workflow governado ausente no HEAD atual deve bloquear o gate.
4. Workflow governado com conclusão `failure`, `cancelled`, `skipped` ou `neutral` deve bloquear o gate.
5. Execução anterior verde no mesmo SHA não pode mascarar uma execução mais recente falha, pendente ou ignorada.
6. Quando o PR alterar `frontend/src/**` ou os scripts/workflow de linguagem simples, `Linguagem simples PT-BR` deve participar da evidência governada no HEAD atual. O workflow `Linguagem simples - autocorreção governada` permanece como remediação `pull_request_target` e não pode ser tratado como evidência universal de merge.
7. Estados pendentes/deferred não podem ser promovidos a sucesso.
8. A mudança não altera produção, deploy, secrets, permissões administrativas ou branch protection.

## Critérios de aceite

- Os contratos de regressão de workflows permanecem verdes.
- Ausência de workflow governado produz estado bloqueante.
- `skipped` ou `neutral` em workflow governado produz estado bloqueante.
- Uma execução mais recente falha prevalece sobre sucesso anterior no mesmo SHA.
- O check `Linguagem simples PT-BR` entra no conjunto avaliado pelo PR Evidence Gate somente quando os caminhos relevantes de frontend forem alterados; PRs fora desse escopo não ficam bloqueados pela ausência do workflow path-scoped.
- O Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato antes da abertura da PR.
- A branch permanece sincronizada com a `main`.

## Evidência

Registrar SHA do HEAD, SHA da base, run do Pre-PR Readiness, estado do PR Evidence Gate e resultados dos workflows governados no mesmo HEAD.

## Rollback

Reverter o commit deste incremento. Não há alteração direta de runtime ou produção.
