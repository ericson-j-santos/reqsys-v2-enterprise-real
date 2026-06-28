# Ambientes e Acesso

> **Versão:** `0.1.0`

## Ambientes conhecidos

| Ambiente | URL | Finalidade | Observação |
|---|---|---|---|
| API pública | `https://reqsys-api.fly.dev` | Backend/API runtime | Validar com `/health` e `/api/runtime/*` |
| Frontend público | `https://reqsys-app.fly.dev` | Aplicação web | Validar login, dashboard e CORS |
| Docs GitHub Pages | `https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/` | Documentação publicada | Depende de merge em `main` e Pages via Actions |
| HTML offline | `docs-site/offline/reqsys-docs-v0.1.0.html` | Fallback sem MkDocs | Versionado no Git |

## Semáforo operacional alvo

| Item | Critério | Estado alvo |
|---|---|---|
| MkDocs build | `mkdocs build --strict` sem erro | Verde |
| PR docs | CI do PR sem falha | Verde |
| Publicação Pages | Deploy após merge em `main` | Verde |
| Fallback HTML | Arquivo offline versionado no Git | Verde |
| Rastreabilidade | Versão + changelog + PR | Verde |

## Estratégia de acesso corporativo

A documentação possui dois modos:

1. **Fonte versionada:** Markdown + MkDocs em `docs-site/`.
2. **Consumo offline:** HTML autocontido em `docs-site/offline/`.

## Restrições

- GitHub Pages precisa estar permitido no repositório.
- O link público definitivo só fica evidenciado após merge e deploy.
- O HTML offline é o fallback mais seguro quando houver bloqueio de Python/MkDocs.
