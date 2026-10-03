# Quality Gates — SQL Visual Explain Stack

## Gates técnicos

| Gate | Critério |
|---|---|
| Testes unitários | `tests/test_sql_visual_explain_analyzer.py` deve passar |
| Script executável | `scripts/sql_visual_explain_analyzer.py` deve gerar Markdown sem erro |
| Documentação | ADR, runbook, release note e changelog devem existir |
| Diagramas | Mermaid/ERD devem estar versionados |
| Segurança | Nenhuma credencial, PII ou connection string em exemplos |

## Gates de maturidade

| Nível | Critério |
|---|---|
| Inicial | Documentação e exemplo versionado |
| Operacional | Script com teste e runbook |
| Enterprise | SQLGlot, CI, EXPLAIN controlado e relatórios gerados |
| Avançado | Integração runtime, analytics e documentação viva automática |

## Status deste incremento

- Nível atingido: **Operacional inicial**.
- Nível alvo seguinte: **Enterprise**.
