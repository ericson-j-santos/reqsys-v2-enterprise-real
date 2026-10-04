# SQL Visual Explain Stack

## Objetivo

Complementar a Query Intelligence Platform com geração offline e versionável de documentação SQL.

## Requisitos

1. O script não pode abrir conexão com banco.
2. O script não pode executar SQL, EXPLAIN ou EXPLAIN ANALYZE.
3. Deve extrair tabelas, joins, filtros e ordenação do caso suportado.
4. Deve sinalizar comandos potencialmente destrutivos.
5. Deve gerar Markdown e Mermaid determinísticos.
6. O lab HTML deve declarar que não é evidência operacional/performance.
7. A superfície interativa canônica continua sendo Query Intelligence.
8. Exemplos devem ser sintéticos e sem segredos/dados reais.
9. EXPLAIN/EXPLAIN ANALYZE real permanece atividade controlada e humana.
10. Nenhum deploy ou alteração de runtime faz parte do incremento.

## Critérios de aceite

- testes do analisador verdes;
- contrato preventivo verde;
- SDD/governança/segurança verdes;
- `behind_by=0`;
- PR sem conflitos e mergeável.
