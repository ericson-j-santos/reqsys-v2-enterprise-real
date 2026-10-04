# Referência — análise inteligente de consultas

A tela `/query-intelligence` recebe uma consulta SQL e apresenta uma interpretação estática.

## Saídas

- intenção lógica resumida;
- tabelas e aliases;
- junções e condição associada;
- filtros;
- agrupamento e ordenação;
- CTEs;
- relações lógicas;
- alertas de desempenho, integridade, segurança e dados pessoais.

## Limites

A ferramenta não executa SQL, não consulta planos reais do banco, não mede custo do otimizador e não substitui revisão técnica. A saída serve como apoio de análise e governança.
