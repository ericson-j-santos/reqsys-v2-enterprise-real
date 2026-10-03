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

## Restauração DEV autorizada

- Comprovar Docker Linux e executor próprio no DESKTOP-PDQK954.
- Localizar por metadados a cópia Restic validada no Noteri; nunca publicar senhas ou registros.
- Transferir somente cópia criptografada autenticada para o destino; manter a senha Restic na origem.
- Restaurar em projeto isolado e conferir todas as tabelas e contagens antes de publicar aplicações.
- Manter o ingresso DEV atual até validar dados, build e autenticação no novo stack.
- Evidências do diagnóstico ficam fora da árvore Git e vinculadas ao SHA e correlation_id.
