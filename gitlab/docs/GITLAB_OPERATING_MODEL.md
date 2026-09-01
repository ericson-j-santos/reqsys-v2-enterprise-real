# ReqSys v2 Enterprise GitLab Edition

## Status atual (2026-08-25) — ver ADR-044

**Esta NÃO é a linha de CI ativa do projeto.** A linha de CI de produção continua sendo exclusivamente o GitHub Actions (`.github/workflows/`).

O projeto GitLab **existe e está provisionado** (remote `gitlab` configurado, `git@gitlab.com:ericson-j-santos/reqsys-v2-enterprise-real.git`). A branch `main` do GitLab está **em dia** com o GitHub `main` (confirmado via `git ls-remote gitlab main` em 2026-08-25, mesmo commit do `origin`/local) — a sincronização deixou de ser um evento manual pontual e passou a acompanhar o GitHub de perto (via `.github/workflows/gitlab-main-mirror.yml`).

**Pipelines já rodaram de fato** (confirmado ao vivo no painel `-/pipelines` em 2026-08-25, 16 execuções) — mas todas falhavam por um bug real: `gitlab_operational_evidence_gate` (`gitlab/ci/evidence.yml`) exigia via `needs:` três jobs (`backend_sast_bandit`, `backend_dependency_scanning_pip_audit`, `frontend_dependency_scanning_npm_audit`) que só existiam condicionalmente (`rules: changes:`), quebrando a criação do pipeline inteiro em qualquer commit fora de `backend/**`/`frontend/**`. Corrigido em 2026-08-25: os três scanners passaram a rodar sempre (removido `rules: changes:` de `gitlab/ci/security.yml` e `gitlab/ci/devsecops.yml`), eliminando a inconsistência com o gate que já os exigia como obrigatórios. Ainda não há confirmação de um pipeline **verde** desde a correção — validar na próxima execução real.

O que já é real (roda de fato, se executado em um runner GitLab):

- `runtime_backend_smoke` roda a suíte de testes do backend com Postgres real (`pytest --cov`).
- `backend_sast_bandit`, `secret_detection_gitleaks`, `backend_dependency_scanning_pip_audit`, `frontend_dependency_scanning_npm_audit`, `container_scanning_trivy` executam ferramentas de segurança reais (não mais `echo "placeholder_ready"`).
- `deploy_staging_fly` roda `flyctl deploy` de verdade — falha explicitamente se `FLY_API_TOKEN` não estiver configurado, em vez de simular sucesso.

O que ainda é placeholder documentado (depende de infraestrutura de um projeto GitLab real para fazer sentido configurar):

- Container scanning (`container_scanning_trivy`) é hoje informativo (`--exit-code 0`), não bloqueante — falta decidir política de severidade antes de virar gate.

**Review apps (item 4) — decidido em 2026-08-25:** ambiente real é **Fly.io**, reaproveitando a mesma credencial já provisionada no cofre para staging (`fly-api-hml-deploy` / variável `FLY_API_TOKEN`, já usada por `deploy_staging_fly`) — nenhuma credencial nova, nenhum provider novo. Um app Fly efêmero por MR (`reqsys-review-mr-$CI_MERGE_REQUEST_IID`), deploy com a mesma config `fly.staging.toml`, destruído ao fechar a MR. Substituiu `review_app_placeholder`/`stop_review_app_placeholder` por `review_app_deploy`/`review_app_stop` reais em `gitlab/ci/environments.yml`. **Não validado contra uma conta Fly real** nesta sessão (sem credencial disponível para testar de ponta a ponta) — rode manualmente uma vez antes de confiar nele para MRs reais. Fly.io não tem mais tier gratuito ilimitado (removido em 2024), mas o custo por app de review é baixo (shared-cpu-1x, auto-stop em 3 dias) e reaproveita infraestrutura/credencial já paga para staging — não introduz gasto novo de plataforma.

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

1. Conectar issues GitLab ao roteador multi-IA. Código pronto em 2026-08-25 (`gitlab/scripts/route_issue_by_label.py`, jobs `gitlab_route_issues_dry_run`/`_apply` em `gitlab/ci/governance.yml`) — falta rodar `_dry_run` uma vez contra issues reais para validar antes de considerar concluído.
2. Criar pipelines semânticos por domínio. **Decisão de design corrigida em 2026-08-25** (a sessão anterior tinha marcado isso como arriscado por engano — ver abaixo). Status real: `runtime_backend_smoke` (`gitlab/ci/runtime.yml`) **já é condicional por domínio** via `rules: changes: [backend/**/*, runtime/**/*, infra/**/*, ...]`, e nada mais no pipeline tem `needs:` nesse job — confirmado com `grep -rn runtime_backend_smoke gitlab/ci/`. Isso já é "pipeline semântico por domínio" funcionando para o domínio `runtime`. O erro da sessão anterior foi generalizar demais: o bug do `needs:` (corrigido no #1306) só existe quando um job condicional é referenciado via `needs:` por OUTRO job que trata sua ausência como falha. **Princípio para estender a outros domínios:** um job pode ser condicional por `rules: changes:` com segurança sempre que (a) nenhum outro job tem `needs:` nele, ou (b) todo `needs:` correspondente usa `optional: true` e o job que precisa dele não trata a ausência como reprovação obrigatória (como faz `validate_gitlab_operational_evidence.py` com os scanners de segurança — por isso esses continuam incondicionais, de propósito). Os domínios `observability`/`ux`/`docs`/`coordinator`/`autonomous` ainda não têm arquivo CI dedicado — quando ganharem, aplicar o mesmo padrão de `runtime.yml`.
3. ~~Adicionar SAST/secret detection/container scanning.~~ Feito (`gitlab/ci/security.yml`, `gitlab/ci/devsecops.yml`).
4. Integrar environments e review apps. Código pronto em 2026-08-25 (`review_app_deploy`/`review_app_stop` em `gitlab/ci/environments.yml`, ambiente Fly.io — ver "Review apps" acima) — falta validar contra uma conta Fly real antes de considerar concluído.
5. ~~Publicar dashboard de evidências GitLab.~~ Feito em 2026-08-25: `gitlab_evidence_dashboard` (`gitlab/ci/evidence.yml`) agrega gate operacional + scanners em `audit/gitlab-evidence-dashboard.html`, autocontido e não bloqueante.
