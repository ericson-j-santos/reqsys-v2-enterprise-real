# Notas de esquema do perfil

Campos obrigatórios do primeiro perfil:

- `profile`: identificador estável do perfil;
- `source.type`: `excel`;
- `source.table`: tabela estruturada do Excel;
- `source.identifier_column`: única coluna lida pelo extrator;
- `source.identifier_pattern`: expressão regular de validação;
- `sql.procedure`: procedure de integração;
- `sql.input_mode`: `json`;
- `sql.key_field`: chave retornada pela consulta;
- `destination.type`: `sharepoint`;
- `destination.list`: lista de destino;
- `destination.business_key`: chave idempotente;
- `destination.operation`: `upsert`;
- controles de governança obrigatórios.

O perfil não deve conter senhas, tokens, cadeias de conexão ou conteúdo confidencial.
