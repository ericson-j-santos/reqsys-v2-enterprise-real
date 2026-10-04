# Requisitos — Inventário de required checks versus workflows reais

## Escopo

Fechar o gap canônico `OPS-GAP-GITOPS-CHECKS-001` (P0 do backlog Pareto enterprise) sem abrir frente paralela de automação de branch protection.

Required status check no GitHub é comparado com o **check run name** publicado no SHA do PR, que corresponde ao `name` do job (ou ao job id quando o job não declara `name`). A linha base canônica do repositório recomendava seis contextos que são nomes de workflow; nenhum deles é publicado como check run. Aplicá-la literalmente travaria todo PR em `Expected — Waiting for status to be reported`.

Fora de escopo: aplicar a proteção real em `Settings > Rules > Rulesets` (exige permissão administrativa) e os demais gaps do backlog Pareto.

## Requisitos funcionais

1. O inventário deve derivar os check run names produzíveis lendo todos os workflows de `.github/workflows`, considerando `name` do job e, na ausência dele, o job id.
2. Os contextos exigidos devem vir do payload real de `required_status_checks` quando disponível e, na sua ausência ou indisponibilidade (`unavailable`), da linha base versionada, com a fonte registrada no relatório.
3. Cada contexto exigido deve ser classificado em `active`, `conditional_risk`, `not_pr_triggered`, `workflow_name_mismatch`, `renamed_candidate` ou `stale`.
4. Filtro de paths no `pull_request`, filtro de branches que exclui a branch alvo, job matricial, nome de job dinâmico, reusable call e `if` condicional devem ser tratados como risco de não materialização; `if` contendo `always()` não é risco.
5. Contexto igual a nome de workflow deve ser classificado como `workflow_name_mismatch` e sugerir os check run names reais daquele workflow.
6. Contexto sem correspondência exata, mas com nome próximo por normalização sem acento e sem separadores, deve ser classificado como `renamed_candidate` com sugestão.
7. Contexto divergente sem decisão registrada deve manter `blocking=true`; decisão registrada (`rename`, `remove` ou `keep`, com `target_contexts`, `rationale`, `owner` e `decided_at`) deve preservar o achado em `stale_contexts` e liberar o bloqueio.
8. A lista recomendada (`recommended_required_contexts`) deve ser validada como controle positivo: se algum contexto recomendado deixar de ser `active`, o relatório bloqueia.
9. Ausência total de contexto exigido deve resultar em `inconclusive=true` com decisão `no_required_contexts_declared`.
10. Workflow não parseável deve ser reportado em `unparsed_workflow_files` sem interromper o inventário.
11. O relatório deve declarar `automatic_branch_protection_change_allowed=false`, `automatic_context_removal_allowed=false` e `production_touched=false`.
12. O script deve ser leitura pura: sem chamada de API, sem alteração de proteção, sem segredo e sem efeito em runtime.
13. Os gaps do backlog Pareto canônico devem estar espelhados em `config/operational-gaps-registry.json` para que `agent_increment_gate.py --increment-type gap_fix --reference OPS-GAP-*` aceite as referências P0/P1.
14. O workflow de CI deve ser report-only: contrato em PR do escopo, inventário agendado e artifact publicado, com `--strict` apenas em `workflow_dispatch`.

## Critérios de aceite

- `python scripts/build_required_checks_stale_inventory.py` classifica os seis contextos declarados como `workflow_name_mismatch`, com sugestão do check run name real de cada um;
- a lista recomendada de oito contextos é validada como `active` contra os workflows reais do repositório;
- sem decisão registrada o relatório retorna `blocking=true`; com decisão registrada retorna `blocking=false` mantendo `stale_contexts` preenchido;
- `python scripts/sdd_gate.py --base-ref main` retorna `SDD_OK`;
- `python -m pytest tests/test_build_required_checks_stale_inventory.py tests/test_operational_gaps_registry_pareto_alignment.py -q` verde, incluindo os controles negativos (`stale`, `renamed_candidate`, matriz, filtro de paths, filtro de branch, workflow inválido, fallback de proteção indisponível);
- `agent_increment_gate.py --increment-type gap_fix --reference OPS-GAP-GITOPS-CHECKS-001` retorna `[PERMITIDO] gap_fix_referenciado`, e referência inexistente continua bloqueada;
- `python scripts/ci_enterprise_guardrails.py` aprovado;
- o gap permanece **parcialmente fechado** até a proteção real refletir os contextos `active` e o inventário rodar com `--strict` sem pendência — aplicação em `Settings` é pendência humana registrada.

## Evidência E2E

Registrar, no maior escopo executável:

- branch, HEAD e base avaliados;
- decisão e resumo do relatório (`decision`, `by_status`, `stale_contexts`, `pending_decisions`, `recommended_all_active`);
- controle positivo (lista recomendada `active`) e controle negativo (decisão ausente bloqueia; referência de gap inexistente bloqueia);
- resultado do gate de incremento antes e depois do espelhamento do backlog;
- suíte `tests/` com a contagem de verdes e a confirmação de que falhas remanescentes são idênticas em `origin/main`.

## Riscos e rollback

- Risco: decisão de renomear contexto aplicada sem conferir o check run name real travaria PR. Mitigação: `recommended_required_contexts` é validado por teste contra os workflows do repositório.
- Rollback: restaurar a lista anterior de contextos (`docs/governance/branch-protection-enterprise-baseline.md` e `config/required-checks-inventory-policy.json` no histórico Git) e desabilitar o workflow report-only. Nada a reverter em runtime, produção, segredo ou permissão.
