# Controle de Escopo — SQL Visual Explain Stack

## Dentro do escopo deste incremento

- Documentar o fluxo didático e enterprise.
- Criar exemplos SQL derivados.
- Criar artefatos de governança.
- Criar script inicial sem dependência externa.
- Criar teste unitário mínimo.
- Criar lab HTML autocontido.

## Fora do escopo deste incremento

- Conectar banco real.
- Rodar `EXPLAIN ANALYZE` automaticamente.
- Adicionar SQLGlot como dependência obrigatória.
- Criar UI integrada ao Runtime Center.
- Publicar em produção.

## Motivo

O objetivo foi aplicar o menor incremento correto, com baixo risco de CI, mantendo base para evolução enterprise no próximo PR.
