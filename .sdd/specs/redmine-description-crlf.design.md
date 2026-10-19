# Design — descrição Redmine CRLF

A normalização ocorre em `montar_campos_requisito_redmine`, na fronteira de
saída. Primeiro CRLF e CR tornam-se LF, depois LF torna-se CRLF. O objeto
Requisito não é modificado. O reconciliador, seu fingerprint e a releitura
literal permanecem intactos, evitando a aceitação de corrupção de conteúdo.

Os testes usam o padrão regex equivalente ao setter upstream como oráculo
independente. O teste real usa o Redmine instalado, não esse oráculo simulado.

A fixture compartilhada importa `app.main` somente quando `client` é
solicitado. A fixture ORM registra os modelos reais explicitamente e mantém
SQLite em memória por teste. Não há app falso, supressão de erro OAuth,
remoção de autenticação ou alteração de dependências de produção.

Rollback: reverter este incremento; não reconectar versões vulneráveis.
Auditoria de mail/rubyzip/sqlite3 permanece pendente e bloqueante.
