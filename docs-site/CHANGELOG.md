# Changelog da Documentação

Todas as mudanças relevantes da documentação viva do ReqSys devem ser registradas neste arquivo.

## [0.5.1] - 2026-06-28

### Adicionado

- Script `runtime/scripts/export_openapi.py` para exportar o OpenAPI gerado pelo FastAPI.
- Contrato gerado e versionado `docs-site/assets/openapi/reqsys-runtime-openapi-v0.5.0.generated.json`.
- Gate de CI para validar drift entre runtime e contrato OpenAPI versionado.
- Testes específicos para garantir presença de metadados ReqSys e rotas de jobs no OpenAPI gerado.

### Alterado

- Workflow `Runtime Async Jobs` passa a validar testes e sincronização OpenAPI.
- README do runtime passa a documentar exportação e validação do contrato gerado.

### Próximo incremento recomendado

- Promover o contrato gerado para contrato canônico `v0.6.0` após estabilizar naming dos operationIds e schemas.
- Adicionar adapter Redis ou Azure Service Bus para substituir a fila local em ambiente DEV integrado.

## [0.5.0] - 2026-06-28

### Adicionado

- Runtime executável inicial em `runtime/` para jobs assíncronos.
- API FastAPI com `POST /api/jobs`, `GET /api/jobs/{job_id}`, `/health`, `/api/runtime/health` e `/api/runtime/analytics`.
- DTOs Pydantic para criação, aceite e consulta de status de job.
- Repositório em memória DEV para primeira fatia executável.
- Fila local baseada em `asyncio.Queue`.
- Worker assíncrono local controlado por feature flag `ENABLE_ASYNC_WORKER`.
- Gateway outbound com `httpx.AsyncClient` e propagação de `X-Correlation-Id`.
- Testes unitários cobrindo criação, consulta e processamento de job.

### Governança

- Mantida compatibilidade com os estados documentados em `v0.4.0`.
- Implementação isolada para reduzir risco de regressão no restante do repositório.
- Próxima troca de infraestrutura deve ocorrer por adapter, sem alterar contratos HTTP.

### Próximo incremento recomendado

- Persistir jobs em banco relacional ou Redis.
- Adicionar workflow CI dedicado para `runtime/`.
- Sincronizar OpenAPI gerado pelo FastAPI com `docs-site/assets/openapi`.

## [0.4.0] - 2026-06-28

### Adicionado

- Documento `docs-site/api/async-httpx-queue.md` com arquitetura assíncrona via API, fila, worker e `httpx.AsyncClient`.
- Contrato OpenAPI versionado `docs-site/assets/openapi/reqsys-runtime-openapi-v0.4.0.json`.
- Endpoints `POST /api/jobs` e `GET /api/jobs/{job_id}` no contrato de runtime.
- Estados operacionais padronizados: `queued`, `processing`, `completed`, `retrying`, `failed` e `dead_letter`.
- Governança mínima para `correlation_id`, retentativas, backoff, dead-letter e rastreabilidade.

### Alterado

- Navegação MkDocs passa a expor o workflow assíncrono HTTPX/Fila.
- Manifesto `VERSION.json` atualizado para `0.4.0` e contrato OpenAPI `v0.4.0`.

### Próximo incremento recomendado

- Implementar fatia executável de runtime com DTOs Pydantic, repositório em memória DEV, worker local controlado por feature flag e testes unitários de transição de estados.

## [0.1.0] - 2026-06-28

### Adicionado

- Configuração inicial `mkdocs.yml`.
- Fonte MkDocs isolada em `docs-site/`.
- Página inicial da documentação.
- Documento inicial de API Runtime.
- Documento operacional de ambientes e acesso.
- Documento de governança e rastreabilidade.
- Manifesto versionado `docs-site/VERSION.json`.
- HTML offline autocontido em `docs-site/offline/reqsys-docs-v0.1.0.html`.
- Workflow `.github/workflows/docs-mkdocs.yml` para build strict, artifact diagnóstico e publicação via GitHub Pages.

### Corrigido

- Evitada varredura da árvore histórica `docs/`, que já contém documentos legados fora de navegação e links internos não normalizados.

### Próximo incremento recomendado

- Integrar OpenAPI/Swagger aos documentos de API.
- Adicionar diagramas Mermaid vivos.
- Renderizar artifacts operacionais JSON dentro da documentação.
