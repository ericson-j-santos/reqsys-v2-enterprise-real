# Changelog da Documentação

Todas as mudanças relevantes da documentação viva do ReqSys devem ser registradas neste arquivo.

## [0.1.0] - 2026-06-28

### Adicionado

- Configuração inicial `mkdocs.yml`.
- Página inicial da documentação em `docs/index.md`.
- Documento inicial de API Runtime.
- Documento operacional de ambientes e acesso.
- Documento de governança e rastreabilidade.
- Manifesto versionado `docs/VERSION.json`.
- HTML offline autocontido em `docs/offline/reqsys-docs-v0.1.0.html`.
- Workflow `.github/workflows/docs-mkdocs.yml` para build strict e publicação via GitHub Pages.

### Decisão

- MkDocs será usado como fonte versionada da documentação viva.
- HTML offline versionado será mantido como fallback para ambientes corporativos sem acesso local ao MkDocs.

### Próximo incremento recomendado

- Integrar OpenAPI/Swagger aos documentos de API.
- Adicionar diagramas Mermaid vivos.
- Renderizar artifacts operacionais JSON dentro da documentação.
