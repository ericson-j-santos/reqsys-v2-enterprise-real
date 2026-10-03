# Pareto — SQL Visual Explain Stack

## 20% que gera 80% do valor

| Prioridade | Ação | Resultado esperado |
|---:|---|---|
| 1 | Explicar Contexto → Missão → Análise → Query → Resultado | Reduz ambiguidade e retrabalho |
| 2 | Documentar tabelas, joins, filtros e ordenação | Facilita revisão técnica e funcional |
| 3 | Gerar Mermaid/ERD versionado | Mantém arquitetura viva |
| 4 | Validar com teste unitário mínimo | Evita regressão no analisador |
| 5 | Planejar SQLGlot como próximo incremento | Eleva precisão sem inflar o primeiro PR |

## Decisão operacional

Não adicionar SQLGlot neste primeiro incremento para evitar risco de CI e dependência nova sem validação prévia.

## Próxima ação ideal

Abrir PR draft, validar CI e depois implementar SQLGlot em PR separado.
