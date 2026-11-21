# ReqSys Control — snapshot exato do frontend AppDeploy

App: `reqsys-control-1y8yvp` · versão publicada: `1795279094826` · [acesso](https://reqsys-control-1y8yvp.v2.appdeploy.ai/)

**Arquivo de recuperação / auditoria, não uma segunda aplicação.** Estes 14 arquivos reproduzem a árvore de fonte do snapshot AppDeploy confirmado em status `ready`. O `source-manifest.json` associa cada arquivo ao blob SHA-1 real do GitHub (Git CAS) lido de volta antes do commit.

Não substituir `tools/reqsys-control/src` por estes arquivos: o frontend principal do GitHub evoluiu em paralelo e inclui `PublicGithubReadOnly`, enquanto o snapshot publicado inclui `GitHubReadOnly`. A reimplementação dos contratos deve ser revisada separadamente para evitar regressão. O arquivo `public/reconciliacao/index.html` deste snapshot foi confirmado idêntico ao arquivo canônico da PR #3160.

Para restaurar em ambiente isolado, usar esta pasta como raiz Vite/React (`npm install` seguido de `npm run build`), após validar versão Node/Vite e dependências. **Não alegar build testado deste checkout**; o snapshot não contém `package-lock.json`, logo `npm ci` não é reproduzível. A aplicação pública foi construída pelo AppDeploy, com QA reportado por ele.

**Segurança:** frontend público, sem acesso autenticado a Redmine/TODO Global. Não inserir tokens, segredos, API keys ou credenciais no JavaScript. O backend já tem `/api/internal/todo-global/queue` com controle JWT admin ou token de serviço `todo_global:read` e código Redmine em `backend/app/services/redmine_api.py`; acesso real e configuração não foram comprovados. Não alterar CORS, autorizar execução nem ligar esta interface diretamente a endpoint privado sem BFF e revisão.

Rastreio: ReqSys issue #3149, PR #3160, GitHub branch antes do arquivo `ceae13fd772a5546819474a54c3def94d8609d35`, regras `main@58dcd4200f412a866278027ba9e433439a03f3b3`. Atualizar esta cópia **somente por novo snapshot identificado**; não sobrescrever a versão.
