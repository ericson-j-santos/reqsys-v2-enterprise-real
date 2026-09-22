# ReqSys Enterprise Docs

> **Versão da documentação:** `0.2.0`  
> **Data:** 28/06/2026  
> **Estado:** Arquitetura Viva inicial versionada.

## Objetivo

Esta documentação consolida a base técnica, operacional e executiva do ReqSys em formato versionado, navegável e compatível com CI.

O objetivo é permitir que arquitetura, APIs, ambientes, governança, rastreabilidade e evidências operacionais sejam mantidos junto do código, reduzindo divergência entre documentação e implementação.

## Acesso sem MkDocs local

Caso o ambiente corporativo não permita instalar Python, MkDocs ou dependências externas, utilize um dos HTMLs estáticos publicados em `/offline/`:

| Versão | Caminho publicado |
|---|---|
| Compatibilidade | `/offline/reqsys-docs-v0.1.0.html` |
| Atual | `/offline/reqsys-docs-v0.2.0.html` |

## Áreas documentadas neste incremento

| Área | Conteúdo | Estado |
|---|---|---|
| Arquitetura Viva | Visão geral e fluxo operacional com Mermaid | Implementado |
| API Runtime | Contrato inicial dos endpoints runtime e requisitos | Inicial versionado |
| Operação | Ambientes, acesso, publicação e fallback | Atualizado |
| Governança | Rastreabilidade, evidências, versionamento e CI | Atualizado |
| Offline | HTML estático sem dependência de MkDocs local | Corrigido |

## Comandos locais opcionais

```bash
pip install -r requirements-docs.txt
mkdocs serve
mkdocs build --strict
```

## Decisão de arquitetura

MkDocs usa `docs-site/` como fonte oficial para evitar varredura da árvore histórica `docs/`, que já possui documentos legados e links internos não normalizados.

## Próximos incrementos recomendados

1. Integrar OpenAPI/Swagger aos documentos de API.
2. Renderizar evidências JSON operacionais dentro do portal de documentação.
3. Adicionar cards executivos por ambiente.
4. Automatizar versionamento semântico por release documental.
