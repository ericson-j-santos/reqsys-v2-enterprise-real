# Release Note — Estatísticas v2

## Tipo

Feature / Backend / Analytics / Governança

## Resumo

A aba Estatísticas passa a consumir um endpoint backend real `GET /v1/estatisticas`, com indicadores calculados sobre dados internos do ReqSys e contrato compatível com a v1.

## Impacto funcional

- A aba deixa de depender apenas de dados locais do frontend.
- Indicadores de requisitos passam a refletir o banco operacional.
- Fontes externas continuam controladas como `nao_medido` até conector real.

## Impacto técnico

- Novo serviço backend de estatísticas.
- Novo router backend `/v1/estatisticas`.
- Integração frontend com API.
- Testes backend e frontend adicionados.

## Riscos residuais

- Histórico temporal ainda não implementado.
- Registry externo real ainda não implementado.
- Métricas de GitHub Actions/PRs/runtime ainda ficam para próximo incremento.

## Decisão operacional

Manter PR em draft até CI completo verde. Após CI verde, pode sair de draft e seguir para merge controlado.
