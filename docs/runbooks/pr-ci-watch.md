# Runbook — PR CI Watch

## Objetivo

Automatizar a leitura de checks e workflow runs associados a um Pull Request, gerando diagnóstico operacional e evidência auditável sem executar merge automático.

## Escopo P0

- Consultar runs de GitHub Actions pelo `head_sha` do PR.
- Excluir a própria execução do watcher quando `GITHUB_RUN_ID` estiver disponível.
- Classificar workflows como `healthy`, `running`, `unhealthy`, `non_blocking` ou `unknown`.
- Calcular score operacional somente sobre checks bloqueantes.
- Gerar artifact JSON e Markdown.
- Opcionalmente comentar o diagnóstico no PR.
- Falhar quando não houver evidência CI suficiente para o SHA.

## Fora do P0

- Merge automático.
- Auto ready-for-review.
- Push de correções automático.
- Execução de comandos em runtime.
- Alteração de produção.

## Arquivos

| Arquivo | Função |
|---|---|
| `.github/workflows/pr-ci-watch.yml` | Workflow executor do watcher. |
| `.github/workflows/ci-fast-operational.yml` | Pipeline rápido de validação operacional. |
| `scripts/pr_ci_watch.py` | Script de classificação e geração de evidência. |
| `tests/test_pr_ci_watch.py` | Testes unitários das decisões do watcher. |
| `docs/runbooks/pr-ci-watch.md` | Este runbook. |

## Acionamentos

| Evento | Comportamento |
|---|---|
| `pull_request` | Analisa o PR atual sem comentar automaticamente. |
| `workflow_dispatch` | Permite informar PR, SHA e se deve comentar. |
| `workflow_run` | Estrutura preparada para evolução, sem mutação automática no P0. |

## Decisões possíveis

| Decisão | Severidade | Significado | Ação recomendada |
|---|---|---|---|
| `pronto_para_revisao` | `ok` | Há check bloqueante concluído com sucesso e nenhum erro. | Revisar e, se aplicável, tirar de draft manualmente. |
| `aguardar_finalizacao_dos_workflows` | `warning` | Há workflows em andamento. | Aguardar nova execução. |
| `corrigir_falhas_antes_de_liberar_revisao` | `critical` | Há workflows falhos, cancelados ou expirados. | Abrir logs e corrigir causa raiz. |
| `investigar_status_desconhecido` | `warning` | Algum workflow retornou estado não mapeado. | Verificar run no GitHub Actions. |
| `sem_evidencia_ci_para_o_sha` | `warning` | Nenhum workflow encontrado para o SHA. | Validar se checks foram disparados e se a branch protection exige check inexistente. |
| `sem_check_bloqueante_conclusivo` | `warning` | Só há checks neutros/skipped, sem evidência verde bloqueante. | Não liberar como verde; ajustar paths/checks obrigatórios. |

## Artifact

Nome:

```text
pr-ci-watch-report
```

Conteúdo:

| Arquivo | Descrição |
|---|---|
| `pr-ci-watch.json` | Payload estruturado com score, severidade, runs e decisão. |
| `pr-ci-watch.md` | Resumo legível para revisão operacional. |

## Política de segurança

- Usa apenas `GITHUB_TOKEN`.
- Não imprime secrets.
- Não executa shell arbitrário informado por usuário.
- Não faz merge automático.
- Não altera draft automaticamente.
- Falha o job quando há workflow unhealthy.
- Falha o job quando não há evidência CI suficiente para o SHA.

## Guardrails contra falso verde

| Risco | Mitigação aplicada |
|---|---|
| Watcher contar a si próprio como `running` | Parâmetro `--exclude-run-id` com `GITHUB_RUN_ID`. |
| PR sem checks aparecer como aceitável | Decisão `sem_evidencia_ci_para_o_sha` retorna erro. |
| `skipped` ser tratado como sucesso | `skipped` vira `non_blocking`, não aumenta score verde. |
| Falha mascarada por workflow neutro | Score considera apenas checks bloqueantes. |

## Operação recomendada

1. Para PRs pequenos, use primeiro `Fast CI - Operational Guardrails`.
2. Só acione revisão profunda depois do fast pipeline verde.
3. Se o watcher retornar `sem_evidencia_ci_para_o_sha`, revise `paths`, branch protection e nomes dos required checks.
4. Se retornar `corrigir_falhas_antes_de_liberar_revisao`, abra o run falho e corrija a causa raiz antes de pedir aprovação humana.
5. Não marque PR como pronto quando a única evidência for `skipped`, `neutral` ou ausência de run.

## Próximo incremento recomendado

- Buscar logs do job falho.
- Classificar causa provável da falha.
- Comentar diagnóstico resumido no PR.
- Evoluir para ready-for-review automático somente quando todos os checks obrigatórios estiverem verdes.
- Integrar ao Operational Actions Center.
