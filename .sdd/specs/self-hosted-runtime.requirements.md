# Requisitos — runtime proprio portavel

Decisao do usuario: elaborar e executar infraestrutura propria para substituir
Fly.io definitivamente em todas as solucoes. OPS-GAP-FLY-RETIREMENT.

## Criterios de aceite
## Critérios de aceite

- Stack Linux independente, configuracao portavel e volumes por projeto.
- HTTPS Caddy; somente ingresso publico; SQL/Redis/API sem portas no host.
- Segredos externos, sem defaults fracos; role SQL da API sem superusuario.
- Frontend compilado e rotas do gateway preservadas.
- Ensaio isolado, backup e restauracao antes da migracao.
- Demo login bloqueado e gates produtivos atuais preservados.
- CI e testes negativos antes de merge.
- Sem declaracao de producao quando host/dominio/dados nao foram validados.
