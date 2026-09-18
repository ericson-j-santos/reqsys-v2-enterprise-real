# Requisitos — probe somente leitura da origem Movimento

## Critérios de aceite
1. Receber somente servidor e banco como parâmetros não secretos.
2. Usar autenticação integrada do Windows, TLS e validação de certificado.
3. Declarar `ApplicationIntent=ReadOnly`.
4. Não aceitar usuário, senha ou DSN completo.
5. Não executar qualquer comando de escrita.
6. Consultar apenas metadados e existência do objeto de Prospecção conhecido.
7. Não imprimir servidor ou banco em texto puro na evidência; usar SHA-256 truncado.
8. Falhar fechado quando conexão ou contrato não puderem ser confirmados.
9. Preferir `ODBC Driver 18 for SQL Server`; aceitar `ODBC Driver 17 for SQL Server` somente mantendo explicitamente TLS, validação de certificado e `ApplicationIntent=ReadOnly`.
10. Quando nenhum ODBC 18/17 estiver disponível, permitir probe equivalente via `Microsoft.Data.SqlClient`, mantendo autenticação integrada, TLS, certificado validado, `ApplicationIntent=ReadOnly` e ausência de segredos.
