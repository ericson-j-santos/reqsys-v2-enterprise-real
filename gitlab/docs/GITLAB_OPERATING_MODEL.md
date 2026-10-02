# ReqSys v2 Enterprise GitLab Edition

## Status atual (2026-10-02) — ver ADR-044

**Esta NÃO é a linha de CI ativa do projeto.** A linha de CI de produção continua sendo exclusivamente o GitHub Actions (`.github/workflows/`).

O projeto GitLab existe como espelho. A retirada definitiva do Fly.io, decidida em 2026-10-02, removeu desta edição todos os includes, jobs de deploy, review apps e provisionamento de token ligados ao provedor. Não há fallback autorizado.

**Pipelines já rodaram de fato** (confirmado ao vivo no painel `-/pipelines` em 2026-08-25, 16 execuções) — mas todas falhavam por um bug real: `gitlab_operational_evidence_gate` (`gitlab/ci/evidence.yml`) exigia via `needs:` três jobs (`backend_sast_bandit`, `backend_dependency_scanning_pip_audit`, `frontend_dependency_scanning_npm_audit`) que só existiam condicionalmente (`rules: changes:`), quebrando a criação do pipeline inteiro em qualquer commit fora de `backend/**`/`frontend/**`. Corrigido em 2026-08-25: os três scanners passaram a rodar sempre (removido `rules: changes:` de `gitlab/ci/security.yml` e `gitlab/ci/devsecops.yml`), eliminando a inconsistência com o gate que já os exigia como obrigatórios. Ainda não há confirmação de um pipeline **verde** desde a correção — validar na próxima execução real.

O que permanece executável, se houver um runner GitLab:

- `runtime_backend_smoke` roda a suíte de testes do backend com Postgres real (`pytest --cov`).
- `backend_sast_bandit`, `secret_detection_gitleaks`, `backend_dependency_scanning_pip_audit`, `frontend_dependency_scanning_npm_audit`, `container_scanning_trivy` executam ferramentas de segurança reais (não mais `echo "placeholder_ready"`).
- `gitlab_environments_baseline` publica somente evidência declarativa de ambientes; não publica aplicações.

O que ainda é placeholder documentado (depende de infraestrutura de um projeto GitLab real para fazer sentido configurar):

- Container scanning (`container_scanning_trivy`) é hoje informativo (`--exit-code 0`), não bloqueante — falta decidir política de severidade antes de virar gate.

**Deploy e Review Apps:** não existem jobs executáveis nesta edição. Uma futura implementação depende de decisão arquitetural e validação do runtime substituto; Fly.io é proibido inclusive como contingência.

Antes de considerar esta edição "em uso": validar a primeira execução real em runner e configurar apenas as variáveis GitLab exigidas pelos gates de governança. Não configurar credenciais do provedor retirado.

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
4. Integrar environments e review apps somente após aprovação do runtime substituto. A baseline atual é report-only e não contém deploy nem fallback Fly.io.
5. ~~Publicar dashboard de evidências GitLab.~~ Feito em 2026-08-25: `gitlab_evidence_dashboard` (`gitlab/ci/evidence.yml`) agrega gate operacional + scanners em `audit/gitlab-evidence-dashboard.html`, autocontido e não bloqueante.
