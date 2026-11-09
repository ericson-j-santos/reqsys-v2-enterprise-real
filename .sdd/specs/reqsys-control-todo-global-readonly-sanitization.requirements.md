# ReqSys Control — leitura privada do TODO Global

## Escopo
O endpoint já existente `GET /api/internal/todo-global/queue` continua protegido por token de serviço limitado ao escopo `todo_global:read` ou administrador autenticado. O frontend público não pode receber credencial Notion; nenhuma ação de host, merge, deploy, restart ou upsert é autorizada por esta especificação.

## Critérios de aceite
1. Exceções internas do Notion, incluindo valores semelhantes a tokens, nunca são devolvidas como `detail` HTTP. Diferenciar 422 genérico para cursor/page_size inválidos e 502 genérico para indisponibilidade.
2. Chamadas sem autorização recebem 401; token apenas de leitura não pode autorizar escrita, inclusive mediante repetição da requisição.
3. Retorno de leitura só possui campos permitidos e `host_admitted=false`. Paginação inconsistente bloqueia o retorno; resultados E2E não devem ser inferidos de `success` de CI.
4. Repetição de consulta não cria tarefas ou alterações na fonte canônica; nenhuma credencial deve aparecer em logs, artefatos ou browser.
5. A superfície do painel requer autenticação do usuário final e segregação RBAC/tenant antes de ativar o consumo de dados privados. Evidência de usuário A não pode ser lida por usuário B.
6. 100% dos gates aplicáveis no SHA final: sintaxe, positivos, negativos, regressão, idempotência, CI real, E2E do fluxo autenticado, leitura independente e controle de custo incremental zero. Sem gates, `BLOQUEADO`.
7. O site continua somente para planejamento até autorização explícita de deploy; sem CORS wildcard, segredo no JavaScript, bypass do Gateway ou publicação pública de dados privados.

## Segregação de acesso ao TODO Global privado

O TODO Global é uma fila administrativa global, sem propriedade de tenant por registro. Não é permitido compartilhar a fila com usuários não administradores, nem inferir visibilidade por usuário a partir do conteúdo de uma issue. A rota `GET /api/internal/todo-global/queue` exige JWT com `papel=admin` ou token S2S autenticado com escopo explícito `todo_global:read`; a permissão coringa `*` não habilita esta leitura. Tokens `todo_global:upsert`, operadores e anônimos devem receber 401/403. O acesso via frontend público e toda integração Notion fora do backend permanecem bloqueados até autenticação e isolamento comprovados, com custo incremental R$ 0,00. A alteração não habilita CORS amplo, nem define RBAC por tenant que não existe na fonte.

### Critérios de aceite adicionais

1. Rejeitar usuários sem perfil admin, tokens sem escopo exato e token `*` com HTTP 401/403 sem consultar Notion.
2. Permitir JWT de admin e token de leitura explícito, preservando separação de `upsert`.
3. Confirmar não regressão da aceitação de wildcard nos outros consumidores já autorizados.
4. Sanitizar erros de integração sem revelar detalhes da exceção, URL interna ou segredo.
5. Não ativar API pública, frontend ou fluxo operacional enquanto CI/E2E, readback e autorização de deploy não forem comprovados.
