# ADR-032 — Operational Health Dashboard Governance

## Status

Aceita.

## Contexto

Após a sequência acelerada de merges, o repositório reduziu significativamente o drift operacional, mas precisa de uma camada permanente para evitar retorno do problema.

O risco principal não é mais criar novas capacidades, e sim manter a fila de PRs curta, classificável, auditável e com decisão objetiva de merge.

## Decisão

Criar uma camada de governança operacional review-only para orientar:

- classificação de PRs;
- fechamento de PRs superseded;
- tratamento de branches antigas;
- leitura executiva de saúde operacional;
- decisão de merge baseada em score.

## Consequências positivas

- Reduz ruído visual em PRs.
- Reduz risco de conflitos recorrentes.
- Melhora rastreabilidade de decisão.
- Acelera publicação controlada.
- Separa experimental, governança e produção.

## Consequências negativas

- Ainda não coleta dados reais automaticamente.
- Depende de disciplina operacional até virar gerador dinâmico.
- Não substitui revisão humana.

## Guardrails

- Sem deploy.
- Sem alteração em produção.
- Sem alteração de permissões.
- Sem alteração de segredos.
- Sem merge automático.
