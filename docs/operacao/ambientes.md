# Ambientes e Acesso

> **Versão:** `0.1.0`  
> **Objetivo:** consolidar links, estados-alvo e fallback de acesso da documentação.

## Ambientes públicos conhecidos

| Ambiente | URL | Finalidade | Observação |
|---|---|---|---|
| API pública | `https://reqsys-api.fly.dev` | Backend/API runtime | Validar com `/health` e rotas `/api/runtime/*` |
| Frontend público | `https://reqsys-app.fly.dev` | Aplicação web | Validar login, dashboard e CORS |
| Docs GitHub Pages | `https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/` | Documentação MkDocs publicada | Depende de merge em `main` e GitHub Pages via Actions |
| HTML offline | `docs/offline/reqsys-docs-v0.1.0.html` | Fallback corporativo sem MkDocs | Versionado no Git |

## Semáforo operacional alvo

| Item | Critério | Estado alvo |
|---|---|---|
| MkDocs build | `mkdocs build --strict` sem erro | Verde |
| PR docs | CI do PR sem falha | Verde |
| Publicação Pages | Deploy após merge em `main` | Verde |
| Fallback HTML | Arquivo offline versionado no Git | Verde |
| Rastreabilidade | Versão + changelog + PR | Verde |

## Estratégia de acesso corporativo

Como ambientes corporativos podem bloquear instalação de dependências, a documentação passa a ter dois modos:

1. **Modo fonte:** Markdown + MkDocs para evolução contínua.
2. **Modo consumo:** HTML autocontido em `docs/offline/` para abertura direta no navegador.

## Validação manual mínima

```bash
python -m pip install --upgrade pip
pip install mkdocs mkdocs-material pymdown-extensions
mkdocs build --strict
```

## Validação por CI

O workflow `.github/workflows/docs-mkdocs.yml` executa:

1. Checkout.
2. Setup Python.
3. Instalação de dependências de documentação.
4. Build strict.
5. Upload de artifact.
6. Deploy GitHub Pages apenas em push para `main`.

## Restrições

- O GitHub Pages precisa estar permitido no repositório.
- O link público de documentação só fica definitivo após merge e deploy.
- O HTML offline é o fallback mais seguro quando houver bloqueio de Python/MkDocs.
