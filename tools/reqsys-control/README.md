# ReqSys Control — frontend governado

Esta pasta preserva a origem de código do site AppDeploy `reqsys-control-1y8yvp` (snapshot `1794108944952`) com o incremento de consulta read-only das issues públicas.

- Regras globais: `chatgpt-operational-rules/main@86abe65b22781c2f608a7d7286ce3a28cd48aaaf` (v1.6.20).
- Base ReqSys: `451f9da9bcc306501c7d00e649956bb765df84b9`.
- Fluxo E2E entre hosts: `e2e-platform#10`, bloqueio `BLOCKED_PHYSICAL_CROSS_HOST_E2E`.
- Fonte canônica TODO Global: Notion privado, não sincronizado; `TODO_GLOBAL_SYNC_PENDING`.
- Não existe autenticação neste site público. Não registrar informações confidenciais.
- Cadastro local em navegador não sincroniza entre computadores. Exportação/importação é apenas transporte manual.
- A leitura pública do GitHub não valida runner, SHA, perfil NORMAL, Gateway, lease, worktree ou custo.
- `ready_for_work` nunca deriva de autodeclaração, estado de issue ou CI verde; apenas recebimento de evidência governada com readback independente.
- Custo máximo incremental: R$ 0,00. Sem dispatch, reboot, Docker, GUI remota, merge, implantação em ambiente, segredos ou mutações administrativas.
- Integração TODO/Notion e sincronização privada exigem backend com autenticação e validação de autorização. Não transportar token para frontend. Aprovação separada antes de qualquer implantação.

## Aceite

1. Verificar que a API GitHub chamada é `GET` em cinco destinos fixos e que nenhum segredo é passado.
2. Positivo: issue pública acessível mostra estado, título e horário da leitura, mas não libera host.
3. Negativo: API indisponível, inválida ou limitada mostra indisponibilidade e mantém bloqueio.
4. Replay: nova consulta não enfileira tarefa nem grava no TODO. Idempotência de registros locais permanece.
5. CI/build e testes de UI no SHA da branch; revalidar depois de cada mudança.

### Desenvolvimento local em ambiente de desenvolvimento isolado

```bash
npm ci
npm run build
```

Esta branch não executa automaticamente publicação do site existente. Atualização do AppDeploy é uma etapa de deploy separada.
