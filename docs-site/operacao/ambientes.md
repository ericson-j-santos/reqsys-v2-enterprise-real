# Ambientes e Acesso

> **Versão:** `0.2.0`

## Ambientes conhecidos

| Ambiente | URL | Finalidade | Observação |
|---|---|---|---|
| API pública | `https://reqsys-api.fly.dev` | Backend/API runtime | Validar com `/health` e `/api/runtime/*` |
| Frontend público | `https://reqsys-app.fly.dev` | Aplicação web | Validar login, dashboard e CORS |
| Docs GitHub Pages | `https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/` | Documentação publicada | Depende de GitHub Pages via Actions |
| HTML offline v0.1.0 | `/offline/reqsys-docs-v0.1.0.html` | Compatibilidade do link antigo | Preservado neste incremento |
| HTML offline v0.2.0 | `/offline/reqsys-docs-v0.2.0.html` | Fallback atual | Versionado neste incremento |

## Semáforo operacional alvo

| Item | Critério | Estado alvo |
|---|---|---|
| MkDocs build | `mkdocs build --strict` sem erro | Verde |
| PR docs | CI do PR sem falha | Verde |
| Publicação Pages | Deploy após merge em `main` | Verde |
| Fallback HTML antigo | `/offline/reqsys-docs-v0.1.0.html` acessível | Verde |
| Fallback HTML atual | `/offline/reqsys-docs-v0.2.0.html` acessível | Verde |
| Rastreabilidade | Versão + PR + manifesto | Verde |

## Estratégia de acesso corporativo

A documentação possui dois modos:

1. **Fonte versionada:** Markdown + MkDocs em `docs-site/`.
2. **Consumo offline:** HTML autocontido em `docs-site/offline/`, publicado pelo Pages em `/offline/`.

## Restrições

- GitHub Pages precisa estar permitido no repositório.
- O link público definitivo só fica evidenciado após merge e deploy.
- O HTML offline é o fallback mais seguro quando houver bloqueio de Python/MkDocs.
