# Checklist — SQL Visual Explain

## Antes da query

- [ ] O objetivo de negócio está claro.
- [ ] As tabelas principais foram identificadas.
- [ ] Os relacionamentos foram confirmados.
- [ ] Os filtros possuem justificativa.

## Durante a query

- [ ] Joins estão explícitos.
- [ ] Filtros não eliminam dados indevidamente.
- [ ] Agregações possuem `GROUP BY` correto.
- [ ] Divisões usam proteção contra zero quando aplicável.
- [ ] Ordenação reflete o objetivo da análise.

## Depois da query

- [ ] Resultado foi validado em amostra.
- [ ] Plano de execução foi analisado quando necessário.
- [ ] Documentação foi versionada.
- [ ] Diagrama/ERD foi atualizado quando aplicável.
- [ ] Riscos e limitações foram registrados.
