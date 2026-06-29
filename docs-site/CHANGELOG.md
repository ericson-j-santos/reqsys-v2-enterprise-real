# Changelog da Documentação

Todas as mudanças relevantes da documentação viva do ReqSys devem ser registradas neste arquivo.

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
