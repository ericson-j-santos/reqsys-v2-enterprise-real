# ReqSys v2 Enterprise GitLab Edition

## Status atual (2026-07-12) — ver ADR-044

**Esta NÃO é a linha de CI ativa do projeto.** A linha de CI de produção continua sendo exclusivamente o GitHub Actions (`.github/workflows/`). Não existe projeto GitLab provisionado nem remote configurado — tudo aqui é scaffolding local, sem runner real por trás.

O que já é real (roda de fato, se executado em um runner GitLab):

- `runtime_backend_smoke` roda a suíte de testes do backend com Postgres real (`pytest --cov`).
- `backend_sast_bandit`, `secret_detection_gitleaks`, `backend_dependency_scanning_pip_audit`, `frontend_dependency_scanning_npm_audit`, `container_scanning_trivy` executam ferramentas de segurança reais (não mais `echo "placeholder_ready"`).
- `deploy_staging_fly` roda `flyctl deploy` de verdade — falha explicitamente se `FLY_API_TOKEN` não estiver configurado, em vez de simular sucesso.

O que ainda é placeholder documentado (depende de infraestrutura de um projeto GitLab real para fazer sentido configurar):

- Review apps por Merge Request (`review_app_placeholder` / `stop_review_app_placeholder` em `gitlab/ci/environments.yml`).
- Container scanning (`container_scanning_trivy`) é hoje informativo (`--exit-code 0`), não bloqueante — falta decidir política de severidade antes de virar gate.

Antes de considerar esta edição "em uso": provisionar o projeto no GitLab, configurar variáveis de CI (`FLY_API_TOKEN` etc.) e validar a primeira execução real em runner (os arquivos foram validados por lint YAML e pelo script de governança local, não por execução real).

## Objetivo

Esta edição prepara o ReqSys para operar nativamente com GitLab como centro de engenharia, governança e DevSecOps.

Fluxo alvo:

```text
Requisito -> GitLab Issue -> Label IA -> Branch -> Merge Request -> Pipeline -> Artifact -> Environment -> Evidência
```

## Domínios multi-IA

| IA | Label | Branch |
|---|---|---|
| Coordenadora | `ia:coordinator` | `coord/*` |
| Runtime | `ia:runtime` | `runtime/*` |
| Observabilidade | `ia:observability` | `observability/*` |
| UX/UI | `ia:ux` | `ux/*` |
| Governança CI | `ia:governance-ci` | `governance/*` |
| Automação | `ia:autonomous` | `agents/*` |
| Docs Vivas | `ia:docs` | `docs/*` |

## Gates obrigatórios

- Pipeline verde antes de merge.
- MR sem conflito.
- Artifact de evidência quando aplicável.
- Escopo pequeno e rastreável.
- Sem alteração fora do domínio sem aprovação.
- Sem tokens, segredos, CPF, PII ou connection string em logs/código.

## Artifacts padrão

- `audit/change-classification.json`
- `audit/gitlab-governance-report.md`
- `audit/gitlab-security-baseline.txt`
- `audit/gitlab-evidence-summary.md`

## Environments previstos

- `development`
- `staging`
- `production`
- `review/*`

## Próximos incrementos

1. Conectar issues GitLab ao roteador multi-IA.
2. Criar pipelines semânticos por domínio.
3. Adicionar SAST/secret detection/container scanning.
4. Integrar environments e review apps.
5. Publicar dashboard de evidências GitLab.
