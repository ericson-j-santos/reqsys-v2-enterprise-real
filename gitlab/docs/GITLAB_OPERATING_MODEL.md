# ReqSys v2 Enterprise GitLab Edition

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
