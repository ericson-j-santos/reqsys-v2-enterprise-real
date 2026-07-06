# Scorecard Executivo — ReqSys Padrão Ouro

## Objetivo

Consolidar a prontidão real do ReqSys em uma visão executiva, rastreável e versionada, permitindo diferenciar:

- estado evidenciado;
- estado alvo;
- bloqueios reais de produção;
- pendências humanas;
- domínios sem automação de evidência;
- próximo incremento recomendado.

Este scorecard complementa o `scripts/prod_readiness_audit.py` e não substitui os gates existentes de CI/CD, segurança, smoke público, revisão humana e ambientes.

## Artefatos gerados

| Artifact | Finalidade |
|---|---|
| `artifacts/prod-readiness-audit.json` | Entrada primária gerada pela auditoria de produção. |
| `artifacts/padrao-ouro-scorecard.json` | Saída estruturada para dashboards, CI e auditoria. |
| `artifacts/padrao-ouro-scorecard.md` | Leitura executiva com semáforo, score, risco e próxima ação. |

## Execução recomendada

```bash
python scripts/prod_readiness_audit.py \
  --output artifacts/prod-readiness-audit.json \
  --markdown-output artifacts/prod-readiness-audit.md

python scripts/padrao_ouro_scorecard.py \
  --input artifacts/prod-readiness-audit.json \
  --output artifacts/padrao-ouro-scorecard.json \
  --markdown-output artifacts/padrao-ouro-scorecard.md
```

Modo bloqueante para pipeline governado:

```bash
python scripts/padrao_ouro_scorecard.py --strict
```

## Domínios avaliados

| Domínio | Peso | Critério principal |
|---|---:|---|
| `security` | 20 | Autenticação segura, demo login desligado, ambiente produtivo explícito. |
| `auth_azure` | 15 | Configuração pública Azure/Entra coerente e callback correto. |
| `runtime` | 15 | Health, readiness, liveness e smoke público. |
| `secrets` | 15 | Presença nominal e revisão humana de secrets sem expor valores. |
| `governance` | 15 | Aprovações, janela, rollback e evidência humana. |
| `dns` | 5 | Domínio corporativo ou recomendação rastreável. |
| `observability` | 5 | Evidência de observabilidade e correlação. |
| `documentation` | 5 | Documentação viva e rastreabilidade. |
| `user_experience` | 5 | UX operacional pronta para usuário final. |

## Semáforo executivo

| Status | Interpretação |
|---|---|
| `ready` | Maturidade >= 95%, sem bloqueios relevantes. |
| `controlled` | Maturidade >= 80%, risco controlado com pendências conhecidas. |
| `attention` | Maturidade >= 60%, ainda há lacunas relevantes. |
| `blocked` | Há bloqueio real ou maturidade insuficiente para produção padrão ouro. |

## Critério canônico para considerar o ReqSys padrão ouro

O ReqSys só deve ser tratado como padrão ouro real quando todos os pontos abaixo estiverem evidenciados:

1. `security`, `auth_azure`, `runtime`, `secrets` e `governance` com score >= 95%.
2. Nenhum domínio obrigatório em `blocked`, `action_required` ou `manual` sem evidência aceita.
3. CI verde e artifacts anexados ao fluxo de PR/deploy.
4. Smoke público validado depois do deploy.
5. Rollback documentado e aprovado.
6. Logs sem PII, senha, token ou connection string.
7. Evidência humana registrada quando a automação não puder comprovar o controle.
8. Changelog, runbook e documentação viva atualizados.

## Decisão de arquitetura

O scorecard foi implementado como script puro e somente-leitura para manter baixo acoplamento com o runtime e permitir uso em três contextos:

- execução local por engenharia;
- CI/CD como quality gate;
- geração de artifact para dashboard executivo.

A decisão evita consultar secrets, bases produtivas ou serviços administrativos diretamente. O scorecard consome o artifact de auditoria já produzido e transforma controles em maturidade executiva.

## Próximo incremento recomendado

Integrar `scripts/padrao_ouro_scorecard.py` a um workflow governado que publique os artifacts JSON/Markdown e falhe somente quando houver domínio obrigatório bloqueado, mantendo permissividade inicial para lacunas de documentação, observabilidade e UX enquanto os checks automatizados forem incorporados progressivamente.
