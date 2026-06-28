# Changelog da Documentação

Todas as mudanças relevantes da documentação viva do ReqSys devem ser registradas neste arquivo.

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
