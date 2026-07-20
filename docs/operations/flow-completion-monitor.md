# Flow Completion Monitor

## Objetivo

Manter aberto todo item que não alcançou com sucesso, evidência e mesma versão a última etapa obrigatória do último ambiente do fluxo.

## Contrato do MVP

- fluxo configurável em `config/flow-completion/`;
- ordem explícita de ambientes e etapas;
- conclusão somente em `prod/post-deploy-validation` para o fluxo inicial;
- validação de `commit_sha` e `evidence_url`;
- identificação de último ponto concluído e próxima etapa esperada;
- estados `PENDING`, `IN_PROGRESS`, `FAILED`, `BLOCKED`, `STALE` e `COMPLETED`;
- relatório JSON auditável por 90 dias;
- execução horária e manual em modo `report-only`.

## Entrada

O coletor deve fornecer uma lista de execuções com `execution_id`, `item_id`, `expected_commit_sha` e eventos ordenáveis por `updated_at`. Cada evento informa ambiente, etapa, status, versão e evidência.

## Saída

O artifact `reqsys-flow-completion-monitor` contém `report.json` com KPIs, itens abertos, último ponto concluído, próxima etapa e tempo sem atividade.

## Guardrails

- não promove ambientes;
- não altera produção;
- não considera workflow intermediário verde como conclusão do fluxo;
- não aceita evidência sem URL ou versão divergente;
- não fecha item cancelado ou incompleto automaticamente.

## Próximo incremento

Substituir a entrada baseline pelo coletor real de GitHub Actions, deploys Fly.io, homologação e runtime health, preservando o mesmo contrato normalizado.
