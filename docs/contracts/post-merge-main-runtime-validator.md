# Post-merge Main Runtime Validator — Contract

## Objetivo

Registrar o contrato operacional do workflow `Post-merge Main Runtime Validator`, responsável por validar evidências críticas após merge na `main` sem alterar runtime, deploy, API, frontend ou banco.

## Escopo

| Item | Contrato |
|---|---|
| Workflow | `.github/workflows/post-merge-main-runtime-validator.yml` |
| Script | `scripts/post_merge_main_runtime_validator.py` |
| Testes | `tests/test_post_merge_main_runtime_validator.py` |
| Artifact publicado | `post-merge-main-runtime-validator` |
| JSON principal | `artifacts/post-merge-main-runtime-validator/post-merge-main-runtime-validator.json` |
| Markdown executivo | `artifacts/post-merge-main-runtime-validator/summary.md` |
| Runtime público padrão | `https://reqsys-app.fly.dev` |

## Entradas observadas

| Fonte | Caminho |
|---|---|
| Smoke governado | `artifacts/runtime-production-smoke-governed.json` |
| Executive runtime summary | `artifacts/executive-runtime-evidence-summary/executive-runtime-evidence-summary.json` |

## Campos de estado operacional

| Campo | Regra |
|---|---|
| `schema_version` | `1.1.0` |
| `evidence_completeness_percentual` | Percentual de checks críticos aprovados |
| `dominant_blocker` | Primeiro check crítico bloqueante ou `none` |
| `automatic_action_possible` | Próxima ação automática reportável pelo workflow |
| `human_action_required` | Ação operacional indispensável quando houver bloqueio ou `none` |

## Gatilhos

| Evento | Comportamento |
|---|---|
| `push` em `main` | Executa validação pós-merge completa |
| `pull_request` para `main` | Executa apenas quando arquivos do contrato mudarem |
| `workflow_dispatch` | Permite validação manual com `base_url` opcional |

## Critérios de sucesso

| Critério | Regra |
|---|---|
| Smoke runtime | `status=healthy` e `required_ok == required_total` |
| Artifact executivo | `contract=executive-runtime-evidence-summary` |
| Estado final | `status=passed` quando todos os checks críticos passam |
| Risco | `low` quando `status=passed`; `high` quando bloqueado |
| Completude de evidência | `100.0` quando todos os checks críticos passam |
| Bloqueio dominante | `none` quando não houver check bloqueante |

## Guardrails

- `post_merge_main_scope`
- `artifact_contract_validation`
- `no_runtime_mutation`
- `reuse_existing_runtime_smoke`

## Links operacionais

- Repositório: <https://github.com/ericson-j-santos/reqsys-v2-enterprise-real>
- Actions: <https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions>
- Runtime público: <https://reqsys-app.fly.dev>

## Fora de escopo

- Não executa deploy.
- Não altera segredo, variável ou configuração de ambiente.
- Não substitui o smoke governado.
- Não duplica Pareto Gate, Human Gate, Executive Brief ou External Signal.
- Não altera contrato funcional da aplicação.

## Status operacional

| Dimensão | Estado alvo |
|---|---|
| Técnico | Verde |
| Operacional | Verde |
| Governança | Verde |
| Produção | Verde |
| Risco residual | Baixo |
