# Workflow operacional — ReqSys Agile Runtime Core

**Data:** 2026-06-25  
**Escopo:** fluxo mínimo para Story → PR/MR → CI → Deploy → Evidência.

## 1. Fluxo principal

```text
novo
→ refinando
→ pronto_para_sprint
→ planejado
→ em_execucao
→ em_revisao
→ em_ci
→ homologacao
→ evidenciado
→ producao
→ monitorado
→ concluido
```

## 2. Estados e gates

| Estado | Entrada permitida quando | Saída permitida quando | Evidência mínima |
|---|---|---|---|
| `novo` | demanda recebida | triagem iniciada | origem da demanda |
| `refinando` | requisito precisa análise | aceite e lacunas definidos | critérios de aceite |
| `pronto_para_sprint` | DoR cumprido | sprint definida | prioridade, estimativa e risco |
| `planejado` | sprint atribuída | execução iniciada | sprint_id e owner |
| `em_execucao` | branch/task ativa | PR/MR aberto | branch e commits |
| `em_revisao` | PR/MR aberto | CI iniciado | URL do PR/MR |
| `em_ci` | pipeline executado | CI aprovado ou reprovado | run_id, status e URL |
| `homologacao` | CI verde | validação funcional concluída | evidência funcional |
| `evidenciado` | evidências anexadas | deploy autorizado | checklist de qualidade |
| `producao` | deploy realizado | monitoramento ativo | ambiente e URL |
| `monitorado` | observabilidade disponível | encerramento autorizado | health/runtime evidence |
| `concluido` | DoD cumprido | reabertura se regressão | fechamento rastreável |

## 3. Estados de exceção

| Estado | Uso | Saída recomendada |
|---|---|---|
| `bloqueado` | dependência externa, conflito, regra pendente ou falha não resolvida | voltar ao estado anterior após remoção do bloqueio |
| `reprovado` | CI, teste, revisão ou homologação falhou | `em_execucao` ou `em_revisao` |
| `cancelado` | item perdeu validade ou foi substituído | encerramento com justificativa |
| `reaberto` | falha pós-conclusão ou evidência invalidada | `refinando` ou `em_execucao` |

## 4. Kanban derivado

| Coluna Kanban | Estados |
|---|---|
| Entrada | `novo`, `refinando` |
| Pronto | `pronto_para_sprint`, `planejado` |
| Execução | `em_execucao` |
| Revisão | `em_revisao` |
| CI/CD | `em_ci` |
| Homologação | `homologacao` |
| Produção | `evidenciado`, `producao`, `monitorado`, `concluido` |
| Exceções | `bloqueado`, `reprovado`, `cancelado`, `reaberto` |

## 5. Mapeamento GitHub/GitLab

| ReqSys | GitHub | GitLab |
|---|---|---|
| Story/Task | Issue ou metadata interna | Issue ou metadata interna |
| Execução | Branch | Branch |
| Revisão | Pull Request | Merge Request |
| CI | GitHub Actions run | GitLab Pipeline |
| Evidência | Checks, artifacts e logs | Jobs, artifacts e logs |
| Deploy | Environment/Release | Environment/Release |

## 6. Métricas mínimas

| Métrica | Fórmula recomendada | Uso |
|---|---|---|
| Completion % | `done_points / committed_points * 100` | saúde da sprint |
| CI pass rate % | `runs_success / runs_total * 100` | qualidade de entrega |
| Lead time | abertura → conclusão | previsibilidade |
| Cycle time | início execução → conclusão | eficiência operacional |
| Throughput | itens concluídos por período | capacidade real |
| Rework rate | reabertos / concluídos | qualidade do refinamento |

## 7. DoR mínimo

Um item só pode ir para `pronto_para_sprint` quando possuir:

- título acionável;
- descrição compreensível;
- critérios de aceite;
- prioridade;
- estimativa inicial;
- risco operacional;
- owner humano ou IA sugerido;
- vínculo com requisito ou demanda origem.

## 8. DoD mínimo

Um item só pode ir para `concluido` quando possuir:

- PR/MR ou justificativa de não código;
- CI com status conhecido;
- evidência de teste ou validação;
- ambiente identificado;
- rastreabilidade completa;
- registro de auditoria.
