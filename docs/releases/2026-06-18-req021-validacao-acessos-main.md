# Release notes — REQ#021 — Validação pública em push na main

## Identificação

| Campo | Valor |
| --- | --- |
| Frente | REQ#021 |
| Branch | `ci/validacao-acessos-main` |
| Tipo | CI / Operação / Documentação |
| Base | `main` |
| Escopo | Automatizar validação pública após merge na branch principal |

## Resumo executivo

Este incremento remove a dependência exclusiva de execução manual ou agendada para a validação de acessos públicos. O workflow passa a executar também em `push` na `main`, permitindo evidência automática após merges.

## Alterações

- Adiciona gatilho `push` para a branch `main` no workflow `.github/workflows/validacao-acessos.yml`.
- Declara permissão mínima `contents: read`.
- Adiciona controle de concorrência por referência GitHub.
- Mantém execução manual por `workflow_dispatch`.
- Mantém execução diária por `schedule`.
- Atualiza `docs/VALIDACAO_ANALITICA_ACESSOS.md` com gatilhos, governança e critério pós-merge.

## Comportamento esperado

| Evento | Resultado esperado |
| --- | --- |
| Merge em `main` | Executar validação pública com `fail_on_unavailable=true` |
| Execução manual | Permitir escolha entre falha bloqueante ou relatório controlado |
| Agenda diária | Gerar evidência recorrente de disponibilidade |

## Evidências esperadas

- Run do workflow `Validação de Acessos Públicos — ReqSys` após push na `main`.
- Artefato `validacao-acessos-publicos.json` publicado pelo job.
- Relatório contendo disponibilidade, status HTTP, tempo médio e quebra por ambiente.

## Rollback

Para rollback, remover o gatilho `push` e o bloco `concurrency` do workflow, mantendo `workflow_dispatch` e `schedule`.
