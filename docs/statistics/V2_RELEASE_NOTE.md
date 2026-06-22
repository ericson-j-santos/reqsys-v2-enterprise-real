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
- Teste de production gate isolado para não depender de variáveis Azure já presentes no CI.

## Riscos residuais

- Histórico temporal ainda não implementado.
- Registry externo real ainda não implementado.
- Métricas de GitHub Actions/PRs/runtime ainda ficam para próximo incremento.

## Correção aplicada após primeira execução do CI

O CI falhou em `test_production_gate_blocks_insecure_defaults` porque o ambiente do workflow já possuía configuração Azure segura. O teste foi corrigido para remover explicitamente `AZURE_TENANT_ID` e `AZURE_CLIENT_ID` quando valida o cenário inseguro.

## Decisão operacional

Manter PR em draft até CI completo verde. Após CI verde, pode sair de draft e seguir para merge controlado.
