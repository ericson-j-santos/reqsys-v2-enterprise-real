# Rastreabilidade da Documentação

> **Versão:** `0.1.0`  
> **Escopo:** governança mínima para documentação viva do ReqSys.

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
| Fonte | Arquivos Markdown em `docs/` |
| Configuração | `mkdocs.yml` |
| Validação | Workflow `.github/workflows/docs-mkdocs.yml` |
| Consumo offline | `docs/offline/reqsys-docs-v0.1.0.html` |
| Histórico | `docs/CHANGELOG.md` |
| Manifesto | `docs/VERSION.json` |
| Revisão | Pull Request |

## Convenção de versão

Usar versionamento semântico para documentação:

```text
MAJOR.MINOR.PATCH
```

Regras:

| Tipo | Quando usar |
|---|---|
| `MAJOR` | Mudança estrutural incompatível na documentação ou navegação |
| `MINOR` | Novo conjunto documental ou nova área relevante |
| `PATCH` | Correções, ajustes textuais e pequenos complementos |

## Política de atualização

Cada incremento documental deve conter:

1. Alteração em Markdown ou HTML offline.
2. Registro em changelog.
3. Validação por `mkdocs build --strict`.
4. PR rastreável.
5. Link de acesso quando publicado.

## Estado atual evidenciado

| Dimensão | Estado |
|---|---|
| Fonte MkDocs | Implementada neste incremento |
| HTML offline versionado | Implementado neste incremento |
| CI de documentação | Implementado neste incremento |
| GitHub Pages | Preparado, depende de merge e deploy |
| Integração OpenAPI | Próximo incremento |
| Diagramas vivos | Próximo incremento |

## Risco mitigado

A inclusão do HTML offline reduz o risco de bloqueio em ambiente corporativo sem acesso a Python, MkDocs ou instalação de pacotes.
