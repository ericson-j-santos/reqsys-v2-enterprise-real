# Flow Completion Monitor

## Objetivo

Manter aberto todo item que não alcançou com sucesso, evidência e mesma versão a última etapa obrigatória do último ambiente do fluxo.

## Contrato

- fluxo configurável em `config/flow-completion/`;
- ordem explícita de ambientes e etapas;
- conclusão somente em `prod/post-deploy-validation` para o fluxo inicial;
- validação de `commit_sha` e `evidence_url`;
- identificação de último ponto concluído e próxima etapa esperada;
- estados `PENDING`, `IN_PROGRESS`, `FAILED`, `BLOCKED`, `STALE` e `COMPLETED`;
- relatório JSON auditável por 90 dias;
- execução horária, manual e após workflows relevantes;
- operação exclusivamente `report-only`.

## Coleta automatizada

O workflow consolida evidências sem duplicar os sistemas de origem:

| Fonte | Evidência normalizada |
| --- | --- |
| GitHub Actions | execução de CI, SHA, resultado, data e URL do run |
| Artifact `fly-homologation-dev` | deploy e smoke de DEV |
| Artifact `fly-homologation-stg` | deploy, integração e homologação de STG |
| Artifact `fly-homologation-prod` | deploy de PROD |
| Endpoints públicos de runtime | health, readiness, liveness e validação pós-deploy de PROD |

Os artifacts são correlacionados ao `workflow_run_id` produtor. O runtime de produção é associado ao SHA do último artifact produtivo concluído com sucesso.

## Entrada normalizada

O coletor produz uma lista com `execution_id`, `item_id`, `expected_commit_sha` e eventos ordenáveis por `updated_at`. Cada evento contém ambiente, etapa, status, versão, origem e URL de evidência.

## Saída

O artifact `reqsys-flow-completion-monitor` contém:

- `report.json`: KPIs, itens abertos, último ponto concluído, próxima etapa e aging;
- `runtime-health.json`: resultado detalhado dos endpoints públicos observados.

## Endpoints de produção observados

- `/health`;
- `/api/runtime/health`;
- `/api/runtime/readiness`;
- `/api/runtime/liveness`.

A etapa final somente recebe sucesso quando todos os endpoints respondem de forma saudável para a versão correlacionada.

## Guardrails

- não promove ambientes;
- não executa deploy;
- não altera produção;
- não considera workflow intermediário verde como conclusão do fluxo;
- não aceita evidência sem URL ou versão divergente;
- não fecha item cancelado ou incompleto automaticamente;
- falha de coleta permanece visível como fluxo aberto ou falho.

## Próximo incremento

Persistir o histórico entre execuções e publicar alertas deduplicados para itens `FAILED`, `BLOCKED` ou `STALE`, mantendo aprovação humana para qualquer remediação.
