# Runbook — PR CI Watch

## Objetivo

Automatizar a leitura de checks e workflow runs associados a um Pull Request, gerando diagnóstico operacional, classificação de falhas e evidência auditável sem executar merge automático.

## Escopo P1

- Consultar runs de GitHub Actions pelo `head_sha` do PR.
- Classificar workflows como `healthy`, `running`, `unhealthy` ou `unknown`.
- Consultar jobs de runs `unhealthy`.
- Identificar steps falhos.
- Classificar causa provável por heurística segura.
- Calcular score operacional.
- Gerar artifact JSON e Markdown.
- Opcionalmente comentar o diagnóstico no PR.

## Fora do P1

- Merge automático.
- Auto ready-for-review.
- Push de correções automático.
- Execução de comandos em runtime.
- Alteração de produção.
- Exposição de logs extensos ou secrets.

## Arquivos

| Arquivo | Função |
|---|---|
| `.github/workflows/pr-ci-watch.yml` | Workflow executor do watcher. |
| `scripts/pr_ci_watch.py` | Script de classificação, falhas e geração de evidência. |
| `docs/runbooks/pr-ci-watch.md` | Este runbook. |

## Acionamentos

| Evento | Comportamento |
|---|---|
| `pull_request` | Analisa o PR atual sem comentar automaticamente. |
| `workflow_dispatch` | Permite informar PR, SHA e se deve comentar. |
| `workflow_run` | Estrutura preparada para evolução, sem mutação automática no P1. |

## Decisões possíveis

| Decisão | Significado | Ação recomendada |
|---|---|---|
| `pronto_para_revisao` | Todos os workflows encontrados estão verdes. | Revisar e, se aplicável, tirar de draft manualmente. |
| `aguardar_finalizacao_dos_workflows` | Há workflows em andamento. | Aguardar nova execução. |
| `corrigir_falhas_antes_de_liberar_revisao` | Há workflows falhos. | Usar classificação de falhas e corrigir causa raiz. |
| `investigar_status_desconhecido` | Algum workflow retornou estado não mapeado. | Verificar run no GitHub Actions. |
| `aguardar_checks_ou_verificar_disparo_de_workflows` | Nenhum workflow encontrado para o SHA. | Validar se checks foram disparados. |

## Classificação de falhas

| Causa provável | Indício | Ação recomendada |
|---|---|---|
| `conflito_de_merge` | Conflict, merge. | Atualizar branch contra `main` e resolver conflitos. |
| `gate_de_governanca` | Governance, quality, guardrail, baseline, security. | Verificar baseline, LGPD, quality gates e documentos de governança. |
| `qualidade_estatica` | Ruff, lint, eslint, typecheck, py_compile. | Corrigir lint, typecheck ou compilação estática. |
| `teste_automatizado` | Test, pytest, unit. | Abrir log do job e corrigir teste ou regressão. |
| `artifact_ausente_ou_invalido` | Artifact, upload. | Garantir geração de arquivos antes do `upload-artifact`. |
| `branch_protection` | Branch protection, ruleset, CODEOWNERS. | Validar ruleset, CODEOWNERS e permissões. |
| `runtime_ou_deploy` | Deploy, Fly, runtime, health. | Validar health, Fly.io e logs operacionais. |
| `falha_nao_classificada` | Sem match. | Abrir log do job falho e classificar manualmente. |

## Artifact

Nome:

```text
pr-ci-watch-report
```

Conteúdo:

| Arquivo | Descrição |
|---|---|
| `pr-ci-watch.json` | Payload estruturado com score, runs, jobs falhos e decisão. |
| `pr-ci-watch.md` | Resumo legível para revisão operacional. |

## Política de segurança

- Usa apenas `GITHUB_TOKEN`.
- Não imprime secrets.
- Não executa shell arbitrário informado por usuário.
- Não faz merge automático.
- Não altera draft automaticamente.
- Falha o job quando há workflow unhealthy.
- Não baixa logs completos no P1.
- Usa apenas metadados de jobs e steps para classificação inicial.

## Próximo incremento recomendado

- Baixar logs resumidos de jobs falhos com mascaramento.
- Criar comentário único atualizável no PR, evitando spam.
- Evoluir para ready-for-review automático quando todos os checks estiverem verdes.
- Integrar ao Operational Actions Center.
