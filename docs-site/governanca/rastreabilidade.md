# Rastreabilidade da Documentação

> **Versão:** `0.1.0`

## Princípios

A documentação do ReqSys deve ser:

- versionada;
- auditável;
- navegável;
- vinculada ao código;
- validada por CI;
- publicável em ambiente web;
- consumível sem dependência local quando necessário.

## Modelo de rastreabilidade

| Item | Evidência esperada |
|---|---|
| Fonte MkDocs | Arquivos Markdown em `docs-site/` |
| Configuração | `mkdocs.yml` |
| Validação | Workflow `.github/workflows/docs-mkdocs.yml` |
| Consumo offline | `docs-site/offline/reqsys-docs-v0.1.0.html` |
| Histórico | `docs-site/CHANGELOG.md` |
| Manifesto | `docs-site/VERSION.json` |
| Revisão | Pull Request |

## Convenção de versão

Usar versionamento semântico:

```text
MAJOR.MINOR.PATCH
```

| Tipo | Quando usar |
|---|---|
| `MAJOR` | Mudança estrutural incompatível |
| `MINOR` | Nova área documental relevante |
| `PATCH` | Correções e pequenos complementos |

## Estado atual evidenciado

| Dimensão | Estado |
|---|---|
| Fonte MkDocs isolada | Implementada em `docs-site/` |
| HTML offline versionado | Implementado |
| CI de documentação | Implementado |
| GitHub Pages | Preparado, depende de merge e deploy |
| Integração OpenAPI | Próximo incremento |
| Diagramas vivos | Próximo incremento |
