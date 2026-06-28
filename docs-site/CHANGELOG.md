# Changelog da Documentação

Todas as mudanças relevantes da documentação viva do ReqSys devem ser registradas neste arquivo.

## [0.3.0] - 2026-06-28

### Adicionado

- Documento `docs-site/api/openapi.md` com visão geral do contrato OpenAPI/Swagger.
- Documento `docs-site/api/power-automate-get-post.md` para prática de fluxos GET/POST no Power Automate.
- Contrato versionado `docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json`.
- Navegação MkDocs para OpenAPI/Swagger e Power Automate GET/POST.

### Governança

- Mantida documentação como artifact vivo, versionado e rastreável.
- Sem alteração de runtime, backend, frontend ou deploy Fly.
- Contrato preparado para validação futura por CI, Postman/Newman ou Spectral.

### Próximo incremento recomendado

- Renderizar o contrato OpenAPI em superfície visual estática compatível com ambientes corporativos restritivos.
- Adicionar validação automática do JSON OpenAPI no CI.

## [0.2.0] - 2026-06-28

### Adicionado

- Seção `Arquitetura Viva` na navegação MkDocs.
- Documento `docs-site/arquitetura/visao-geral.md`.
- Documento `docs-site/arquitetura/fluxo-documentacao-viva.md`.
- Diagramas Mermaid versionados para documentação viva.
- Fallback offline atual `docs-site/offline/reqsys-docs-v0.2.0.html`.
- Compatibilidade do fallback anterior `docs-site/offline/reqsys-docs-v0.1.0.html`.

### Corrigido

- Correção de caminhos do fallback offline em páginas principais da documentação.

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
