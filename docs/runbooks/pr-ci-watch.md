# Runbook — PR CI Watch

## Objetivo

Automatizar a leitura de checks e workflow runs associados a um Pull Request, gerando diagnóstico operacional e evidência auditável sem executar merge automático.

## Escopo P0

- Consultar runs de GitHub Actions pelo `head_sha` do PR.
- Classificar workflows como `healthy`, `running`, `unhealthy` ou `unknown`.
- Calcular score operacional.
- Gerar artifact JSON e Markdown.
- Opcionalmente comentar o diagnóstico no PR.

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
| `scripts/pr_ci_watch.py` | Script de classificação e geração de evidência. |
| `docs/runbooks/pr-ci-watch.md` | Este runbook. |

## Acionamentos

| Evento | Comportamento |
|---|---|
| `pull_request` | Analisa o PR atual sem comentar automaticamente. |
| `workflow_dispatch` | Permite informar PR, SHA e se deve comentar. |
| `workflow_run` | Estrutura preparada para evolução, sem mutação automática no P0. |

## Decisões possíveis

| Decisão | Significado | Ação recomendada |
|---|---|---|
| `pronto_para_revisao` | Todos os workflows encontrados estão verdes. | Revisar e, se aplicável, tirar de draft manualmente. |
| `aguardar_finalizacao_dos_workflows` | Há workflows em andamento. | Aguardar nova execução. |
| `corrigir_falhas_antes_de_liberar_revisao` | Há workflows falhos. | Abrir logs e corrigir causa raiz. |
| `investigar_status_desconhecido` | Algum workflow retornou estado não mapeado. | Verificar run no GitHub Actions. |
| `aguardar_checks_ou_verificar_disparo_de_workflows` | Nenhum workflow encontrado para o SHA. | Validar se checks foram disparados. |

## Artifact

Nome:

```text
pr-ci-watch-report
```

Conteúdo:

| Arquivo | Descrição |
|---|---|
| `pr-ci-watch.json` | Payload estruturado com score, runs e decisão. |
| `pr-ci-watch.md` | Resumo legível para revisão operacional. |

## Política de segurança

- Usa apenas `GITHUB_TOKEN`.
- Não imprime secrets.
- Não executa shell arbitrário informado por usuário.
- Não faz merge automático.
- Não altera draft automaticamente.
- Falha o job quando há workflow unhealthy.

## Próximo incremento recomendado

- Buscar logs do job falho.
- Classificar causa provável da falha.
- Comentar diagnóstico resumido no PR.
- Evoluir para ready-for-review automático quando todos os checks estiverem verdes.
- Integrar ao Operational Actions Center.
