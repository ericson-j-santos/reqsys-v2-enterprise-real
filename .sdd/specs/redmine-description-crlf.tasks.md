# Tarefas — descrição Redmine CRLF

- [x] Reproduzir diferença de 194/204 caracteres e confirmar setter upstream.
- [x] Canonicalizar somente a descrição e manter releitura estrita.
- [x] Implementar controles de conteúdo, espaços, linhas vazias e replay.
- [x] Executar E2E real no candidato inicial 19905ca8, com leitura SQLite
  independente: Redmine run 39173720892/job 117811987806. Etapa funcional
  aprovada; auditoria do bundle reprovada. Não é evidência do próximo SHA.
- [x] Corrigir lint do novo teste e separar coleta ORM da inicialização HTTP.
- [ ] Revalidar pytest completo selecionado pelo Pre-PR no HEAD final.
- [ ] Reexecutar E2E real no HEAD final após alterações de testes/documentação.
- [ ] Concluir revisão/gates antes da integração; não habilitar bypass.
- [ ] Corrigir dependências vulneráveis em incremento com compatibilidade e
  repetir auditoria antes de publicação, respeitando dados e autorização.
