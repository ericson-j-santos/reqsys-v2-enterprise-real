# Tolerância a workflows obrigatórios com filtro de paths — Requisitos

## Contexto

A fila de merge governada avalia, no SHA exato do PR, se os workflows críticos
foram registrados. A policy `governance/merge/current-sha-required-workflows.json`
lista esses workflows e declara, em `optional_when_not_registered`, quais podem
estar ausentes sem bloquear o PR.

Um workflow obrigatório cujo gatilho `pull_request` tem filtro de `paths` só
dispara quando o PR toca esses caminhos. Se ele não constar da tolerância, todo
PR que não os toca fica com o workflow em estado `missing`, o job
`Estabilidade dos workflows no SHA atual` retorna `required_workflows_not_registered`
e o `Gate de merge governado` falha — um bloqueio sistêmico do repositório, não
uma reprovação de mérito do PR.

## Requisito 1 — tolerância coerente com o gatilho real

Todo workflow obrigatório com filtro de `paths` no gatilho `pull_request` deve
constar em `optional_when_not_registered`.

## Requisito 2 — tolerância restrita

Nenhum workflow obrigatório sem filtro de `paths` pode constar em
`optional_when_not_registered`: um gate que sempre dispara jamais pode ser
dispensado por ausência.

## Requisito 3 — tolerância não é dispensa de resultado

A tolerância cobre apenas a ausência do registro. Quando o workflow dispara, sua
conclusão continua obrigatória: execução com `failure` mantém o PR bloqueado.

## Critérios de aceite (Acceptance Criteria)

1. Com a policy anterior, um SHA sem `Minimum Controlled Version Gate` registrado
   produz `stable=false` e `decision=required_workflows_not_registered`.
2. Com a policy corrigida, o mesmo SHA produz `stable=true` e `decision=stable`.
3. Com a policy corrigida, um SHA em que `Minimum Controlled Version Gate` executou
   e concluiu como `failure` produz `stable=false` e
   `decision=required_workflows_failed`.
4. O teste de coerência falha enquanto existir workflow obrigatório com filtro de
   `paths` fora de `optional_when_not_registered`.
5. O teste de coerência falha se um workflow sem filtro de `paths` for adicionado
   a `optional_when_not_registered`.
6. `optional_when_not_registered` permanece subconjunto de `required_workflows`.
