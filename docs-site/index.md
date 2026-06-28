# ReqSys Enterprise Docs

> **Versão da documentação:** `0.1.0`  
> **Data:** 28/06/2026  
> **Estado:** incremento inicial versionado para documentação viva.

## Objetivo

Esta documentação consolida a base técnica, operacional e executiva do ReqSys em formato versionado, navegável e compatível com CI.

O objetivo é permitir que arquitetura, APIs, ambientes, governança, rastreabilidade e evidências operacionais sejam mantidos junto do código, reduzindo divergência entre documentação e implementação.

## Acesso sem MkDocs local

Caso o ambiente corporativo não permita instalar Python, MkDocs ou dependências externas, utilize o HTML estático versionado localizado em `docs/offline/reqsys-docs-v0.1.0.html`.

Esse arquivo é autocontido, versionado no Git e pode ser usado como fallback de leitura.

## Áreas documentadas neste incremento

| Área | Conteúdo | Estado |
|---|---|---|
| API Runtime | Contrato inicial dos endpoints runtime e requisitos | Inicial versionado |
| Operação | Ambientes, acesso, publicação e fallback | Inicial versionado |
| Governança | Rastreabilidade, evidências, versionamento e CI | Inicial versionado |
| Offline | HTML estático sem dependência de MkDocs local | Implementado |

## Comandos locais opcionais

```bash
pip install -r requirements-docs.txt
mkdocs serve
mkdocs build --strict
```

## Decisão de arquitetura

MkDocs usa `docs-site/` como fonte oficial para evitar varredura da árvore histórica `docs/`, que já possui documentos legados e links internos não normalizados.

## Próximos incrementos recomendados

1. Adicionar diagramas Mermaid vivos para arquitetura e runtime.
2. Publicar automaticamente via GitHub Pages após merge em `main`.
3. Integrar OpenAPI/Swagger aos documentos de API.
4. Renderizar evidências JSON operacionais dentro do portal de documentação.
5. Criar versionamento semântico por release de documentação.
