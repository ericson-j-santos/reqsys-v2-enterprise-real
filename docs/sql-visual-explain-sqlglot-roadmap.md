# Roadmap — SQLGlot no SQL Visual Explain Stack

## Estado atual

O incremento atual entrega parser heurístico sem dependência externa, documentação operacional, ADR, runbook, lab HTML, exemplos e testes.

## Estado alvo

Adicionar SQLGlot como camada real de parser SQL para:

- Extrair AST.
- Identificar tabelas e colunas com maior precisão.
- Mapear joins, filtros, agregações e ordenações.
- Gerar linhagem de dados.
- Suportar múltiplos dialetos SQL.
- Gerar documentação Mermaid/Markdown automaticamente.

## Incrementos sugeridos

### P0.1 — Parser real

- Adicionar dependência SQLGlot.
- Criar adaptador `SqlGlotQueryAnalyzer`.
- Manter fallback heurístico.
- Criar testes para SELECT, JOIN, WHERE, GROUP BY, CTE e subquery.

### P0.2 — Mermaid automático

- Gerar fluxo lógico Mermaid.
- Gerar ERD simplificado quando relações forem detectadas.
- Versionar saída em `docs/generated/`.

### P0.3 — EXPLAIN controlado

- Criar executor PostgreSQL opcional.
- Exigir variável de ambiente para conexão.
- Bloquear produção por padrão.
- Registrar evidência em Markdown.

### P0.4 — UI operacional

- Integrar ao Runtime Center.
- Permitir colar query, analisar e navegar por tabelas, filtros e riscos.
