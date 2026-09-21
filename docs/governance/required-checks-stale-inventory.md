# Required Checks Stale Inventory

Gap canônico: `OPS-GAP-GITOPS-CHECKS-001` (P0 em `docs/padrao-ouro/enterprise-gap-closure-matrix.json`).

## Problema

Branch protection compara o contexto obrigatório com o **check run name** publicado no SHA do PR. O check run name é o `name` do job (ou o job id, quando o job não declara `name`) — nunca o nome do workflow. Um contexto obrigatório sem produtor real nunca é reportado e o PR fica permanentemente em `Expected — Waiting for status to be reported`, sem falha visível e sem caminho de merge.

O inventário existente (`Required Checks Materialization Inventory`) amostra apenas PRs **já mergeados**, que por definição satisfizeram os checks obrigatórios. Ele não detecta contexto obsoleto, renomeado ou impossível de materializar — esse é o ponto cego fechado por este incremento.

## Estado evidenciado (2026-09-21)

Execução local de `scripts/build_required_checks_stale_inventory.py` sobre `562` workflows (`653` check run names produzíveis):

| Contexto declarado na linha base | Classificação | Contexto real sugerido |
| --- | --- | --- |
| `Governança Padrão Ouro` | `workflow_name_mismatch` | `Validar artefatos de governança` |
| `Governance Quality Gates` | `workflow_name_mismatch` | `governance-validation` |
| `CI — ReqSys v2 Enterprise` | `workflow_name_mismatch` | `CI Router Result` |
| `CI Enterprise Fast` | `workflow_name_mismatch` | `Sumario CI Enterprise Fast` |
| `Branch Protection Audit` | `workflow_name_mismatch` | `Auditar proteção enterprise da branch` |
| `Governed Merge Queue` | `workflow_name_mismatch` | `Gate de merge governado` |

Decisão do relatório: `stale_or_misnamed_required_checks_detected`. Todos os `6` contextos documentados como linha base eram nomes de workflow; nenhum deles existia como check run name. A lista recomendada (8 contextos) foi validada como `active` — cada um tem job produtor disparado por `pull_request` para `main`, sem filtro de paths, sem matriz e com reporte determinístico.

## Decisão registrada

`config/required-checks-inventory-policy.json` registra, para cada contexto divergente, `decision=rename`, o `target_contexts` comprovado, `rationale`, `owner` (`Platform Engineering / CI Governance`) e `decided_at`. Enquanto existir contexto divergente sem decisão registrada, o relatório fica `blocking=true` e `--strict` falha.

Nenhuma alteração de branch protection é feita por automação: `automatic_branch_protection_change_allowed=false` e `automatic_context_removal_allowed=false`. A aplicação em `Settings > Rules` continua sendo ação humana administrativa.

## Classificações

| Status | Significado | Ação |
| --- | --- | --- |
| `active` | Job produtor dispara em PR para a branch alvo, sem filtro de paths, sem matriz e com reporte determinístico | manter |
| `conditional_risk` | Produtor existe, mas é filtrado por paths, condicional sem `always()`, matricial, com nome dinâmico ou reusable call | não usar como obrigatório sem decisão |
| `not_pr_triggered` | Contexto existe, mas nenhum produtor dispara em PR para a branch alvo | remover ou ajustar trigger |
| `workflow_name_mismatch` | Contexto é nome de workflow, não check run name | renomear para o job real |
| `renamed_candidate` | Sem correspondência exata, mas com check run name próximo | renomear |
| `stale` | Nenhum workflow produz esse check run name | remover |

## Execução

```bash
# inventário a partir da linha base versionada (não exige permissão administrativa)
python scripts/build_required_checks_stale_inventory.py

# inventário com branch protection real (exige token com permissão de leitura da proteção)
gh api repos/ericson-j-santos/reqsys-v2-enterprise-real/branches/main/protection/required_status_checks > .tmp/protection.json
python scripts/build_required_checks_stale_inventory.py --protection .tmp/protection.json --strict

# contrato
python -m pytest tests/test_build_required_checks_stale_inventory.py tests/test_operational_gaps_registry_pareto_alignment.py -q
```

Saídas: `artifacts/required-checks-stale-inventory/report.json` e `report.md`. O workflow `Required Checks Stale Inventory` roda o contrato em PR que toque o escopo, gera o inventário diariamente e publica o artifact; `--strict` só é aplicado por `workflow_dispatch` com `strict=true`.

## Ciclo de vida da política

1. Inventário classifica os contextos declarados.
2. Divergência recebe decisão registrada (`rename`, `remove` ou `keep`) com owner e data.
3. Administrador aplica a decisão em `Settings > Rules > Rulesets` (ou branch protection).
4. `declared_required_contexts` é atualizado para refletir a proteção aplicada e a decisão correspondente é removida da política.
5. `recommended_required_contexts` permanece como controle positivo: o contrato falha se algum contexto recomendado deixar de materializar (por exemplo, após renomear um job).

## Rollback

- Restaurar a lista anterior de contextos obrigatórios documentada na versão anterior de `docs/governance/branch-protection-enterprise-baseline.md` e em `config/required-checks-inventory-policy.json` (histórico Git).
- Desabilitar o workflow `Required Checks Stale Inventory` (report-only, sem efeito sobre merge).
- Nenhum rollback de produção é necessário: o incremento não altera runtime, proteção, segredo ou permissão.

## Pendências

- Leitura da branch protection real depende de token com permissão administrativa; enquanto indisponível, o relatório usa `versioned_baseline` e marca a fonte (`versioned_baseline_protection_unavailable`).
- Aplicação das decisões `rename` em `Settings` é pendência humana registrada; o gap `OPS-GAP-GITOPS-CHECKS-001` só fecha quando a proteção real refletir os contextos `active` e o relatório rodar com `--strict` sem pendência.
