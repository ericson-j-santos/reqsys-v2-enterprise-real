# Tarefas — Report Builder Email Delivery

- [x] Registrar issue #2027.
- [x] Definir contrato de entrada com destinatários, assunto, corpo e dry-run.
- [x] Implementar serviço de geração + MIME + anexo RDL.
- [x] Expor endpoint autenticado na aplicação.
- [x] Adicionar testes positivo, negativo e rota FastAPI.
- [ ] Validar CI/Pre-PR no HEAD exato.
- [ ] Executar o endpoint em runtime DEV com `dry_run=true`.
- [ ] Executar envio real para `ericson.takay@gmail.com`.
- [ ] Confirmar entrega por leitura independente do destino e registrar correlation_id/SHA-256.
