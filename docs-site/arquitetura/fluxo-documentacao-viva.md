# Fluxo da Documentação Viva

> **Versão:** `0.2.0`

## Fluxo operacional

```mermaid
sequenceDiagram
    participant Dev as Desenvolvedor
    participant Repo as GitHub Repo
    participant CI as GitHub Actions
    participant Docs as MkDocs
    participant Pages as GitHub Pages
    participant User as Usuario corporativo

    Dev->>Repo: Abre PR versionado
    Repo->>CI: Dispara validacoes
    CI->>Docs: Executa mkdocs build --strict
    Docs-->>CI: Site estatico + fallback offline
    CI->>Pages: Publica apos merge em main
    User->>Pages: Acessa documentacao online
    User->>Pages: Acessa offline/reqsys-docs-v0.1.0.html
```

## Fluxo de compatibilidade offline

```mermaid
flowchart TD
    A[Usuario acessa GitHub Pages] --> B{Ambiente permite internet?}
    B -- Sim --> C[Portal MkDocs online]
    B -- Parcial --> D[HTML offline publicado em /offline]
    B -- Nao --> E[Arquivo HTML baixado do repositorio]
    C --> F[Leitura navegavel]
    D --> F
    E --> F
```

## Regras de manutenção

| Regra | Descrição |
|---|---|
| Versionar sempre | Toda mudança deve atualizar `VERSION.json` e `CHANGELOG.md` |
| Manter fallback | Todo release documental deve preservar HTML offline |
| Build strict | Nenhuma publicação deve passar sem `mkdocs build --strict` |
| Não quebrar link antigo | O caminho `offline/reqsys-docs-v0.1.0.html` deve continuar válido |
| Evidenciar | PR deve registrar o estado implementado, validado e pendente |

## Próxima evolução

O próximo incremento deve integrar OpenAPI/Swagger e artifacts JSON operacionais ao portal MkDocs.
