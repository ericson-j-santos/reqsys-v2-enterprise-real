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
npm install --no-audit
npm run build
```

Esta branch não executa automaticamente publicação do site existente. Atualização do AppDeploy é uma etapa de deploy separada.


**Reprodutibilidade:** o snapshot original do AppDeploy não inclui `package-lock.json`. O lockfile deve ser gerado, revisado e versionado em ambiente isolado antes de exigir `npm ci` em CI. Build e E2E do checkout GitHub ainda não foram executados.


## Contrato de leitura privada preparado (não publicado)

O backend ReqSys existente em `backend/app/api/todo_global_adapter.py` foi estendido com:
- `GET /api/internal/todo-global/queue`, que exige JWT de administrador do ReqSys **ou** token de serviço com escopo exclusivo `todo_global:read`.
- Busca paginada no **Notion real via servidor**, com credenciais no cofre existente, resposta mínima de TODOs não terminais, validação de cursores e erros fail-closed.
- O campo `host_admitted=false` não pode ser substituído pelo frontend.
- Testes em `backend/tests/test_todo_global_queue_readonly.py` cobrem positivos, negativos, replay e acesso não autenticado. Não houve prova física nem leitura real via esse endpoint nesta branch.

**Não conectar o site público diretamente à API privada com credencial no JavaScript.**
A futura interface autenticada precisa ser publicada em origem autorizada (ou por BFF confiável), reutilizar a política de identidade do ReqSys e exigir E2E real + readback, custos verificados e autorização de deploy. Não modificar CORS para `*` nem usar token em localStorage.

**Risco conhecido de integração:** `.github/workflows/reqsys-control-static-qa.yml` foi adicionado antes da releitura da política `docs/ci/WORKFLOW_SURFACE_BUDGET.md`. A política proíbe aumento líquido de workflows; sua exclusão na branch e substituição pela QA canônica de Pre-PR exigem tratamento de mudança revisável, sem enfraquecer o gate. Até isso ocorrer, `READY_FOR_PR` é bloqueado.
