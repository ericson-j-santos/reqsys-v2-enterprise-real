# Requisitos — runtime proprio portavel

Decisao do usuario: elaborar e executar infraestrutura propria para substituir
Fly.io definitivamente em todas as solucoes. OPS-GAP-FLY-RETIREMENT.

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

## Fonte atual e preservação das integrações

- O diagnóstico físico do gateway DEV no PC24x7 comprovou PostgreSQL como fonte atual.
- A cópia SQLite do Noteri pertence a outra base: seu ensaio isolado não autoriza substituir o PostgreSQL ativo.
- Preservar um backup lógico consistente do PostgreSQL atual, protegido no host, e validar restauração, schema, sequências, contagens e conteúdo antes do corte.
- Contagens observadas antes/depois do pg_dump não constituem contagens vinculadas ao snapshot; essa vinculação exige restauração e leitura independente.
- Preservar o JWT_SECRET original usado no HMAC dos tokens de serviço, o cofre-keyring.enc, sua passphrase e service name, e as chaves do histórico cifrado.
- A transferência de configuração não publica valores, hashes de chaves privadas, tokens ou linhas do banco nos logs/artefatos.
- Manter a UI e callback Pages existentes; a API candidata deve aceitar explicitamente a origem Pages.
- Supervisor, reconciliação, túneis e locator devem reconhecer o modo portátil validado e impedir retorno automático ao stack legado.
- A manutenção do stack é uma prova distinta da sessão Microsoft real e do ingresso público; os três resultados precisam permanecer separados.
- O Owner Gateway mantém a negação padrão; ações locais críticas usam autorizações específicas, temporárias, vinculadas ao código revisado.

O ensaio PostgreSQL usa o arquivo DPAPI da base atual, restaura apenas candidato vazio e inativo, verifica COPY por conteúdo e estado de sequências. A configuração exige fidelidade exata de JWT, issuer/audience, cofre e chave de histórico. Prova de sessão Azure exige IdToken explicitamente provisionado e controles negativos; teste de callback interativo permanece separado. Nenhum resultado de preparação permite cutover sem prova recente de congelamento da origem e validação do ingresso público.
