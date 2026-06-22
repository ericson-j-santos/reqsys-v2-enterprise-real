# Checklist de Validação — Aba Estatísticas

## Implementação

- [x] Criar contrato de indicador estatístico.
- [x] Criar serviço inicial de estatísticas.
- [x] Criar tela navegável da aba Estatísticas.
- [x] Registrar rota `/estatisticas`.
- [x] Registrar item no menu principal.
- [x] Adicionar testes unitários de guard rails.
- [x] Registrar notas de implementação.

## Validação pendente de CI

- [ ] Executar testes unitários do frontend.
- [ ] Executar build do frontend.
- [ ] Executar smoke test da navegação.
- [ ] Executar E2E responsivo.

## Critérios de bloqueio para produção

- [ ] Não publicar se indicador sem fonte aparecer como válido.
- [ ] Não publicar se indicador sem fórmula aparecer como válido.
- [ ] Não publicar se mock externo for exibido como fonte real.
- [ ] Não publicar se estado `avancado` for atribuído sem evidência suficiente.
- [ ] Não publicar se houver regressão em rota/menu.
