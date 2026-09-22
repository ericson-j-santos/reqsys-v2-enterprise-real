# Changelog

## 1.1.0 - 2026-09-04

- Substitui dados demonstrativos por processos reais fora do ReqSys.
- Adiciona rastreabilidade por `origem` e `estado_evidenciado_em`.
- Adiciona `historico.json` idempotente por data, limitado aos últimos 365 registros.
- Restaura histórico do artefato anterior no GitHub Actions com `actions: read`.
- Adiciona aba `Historico` ao XLSX.
- Amplia a suíte para 11 testes cobrindo histórico e rastreabilidade.

## 1.0.0 - 2026-09-03

- Cria o Personal Process Control v1 isolado do domínio funcional do ReqSys.
- Adiciona validação de governança para próxima ação, evidência e bloqueios.
- Adiciona priorização Pareto de demandas e automações.
- Adiciona revisão diária e modo semanal aprofundado nas segundas-feiras.
- Gera snapshot JSON, Pareto JSON, relatório Markdown e XLSX determinístico.
