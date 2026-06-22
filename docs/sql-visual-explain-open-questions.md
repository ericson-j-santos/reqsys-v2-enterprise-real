# Perguntas Abertas — SQL Visual Explain Stack

## Técnicas

1. O SQLGlot deve ser dependência obrigatória ou opcional com fallback heurístico?
2. Os relatórios gerados devem ficar em `docs/generated/` ou como artefatos de pipeline?
3. O EXPLAIN controlado deve aceitar apenas PostgreSQL no primeiro momento?
4. A UI operacional deve ficar no Runtime Center ou em aba própria de Query Intelligence?

## Governança

1. Quem aprova execução de `EXPLAIN ANALYZE` em ambiente compartilhado?
2. Qual política de retenção dos relatórios de análise SQL?
3. Como mascarar colunas sensíveis identificadas por nome?
4. Quando uma query pode ser marcada como validada?
