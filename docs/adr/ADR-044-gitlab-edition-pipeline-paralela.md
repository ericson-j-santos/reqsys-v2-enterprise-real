# ADR-044 — GitLab Edition: Pipeline Paralela Fortalecida, Não-Ativa

## Status

Aceito

## Contexto

O repositório contém uma "GitLab Edition" local (`.gitlab-ci.yml`, `.gitlab/`, `gitlab/ci/`, `gitlab/docs/`, `gitlab/scripts/`), criada em 2026-06-25 (PRs #280, #281, #284, #287) como experimento paralelo à linha de CI ativa do projeto, que é o GitHub Actions (`.github/workflows/`, ~160 workflows).

Levantamento em 2026-07-12 mostrou que:

- **Não existe projeto GitLab real conectado.** O único remote do repositório é `origin` → GitHub. As URLs `gitlab.com` encontradas no código são fixtures de teste (`test_git_parser.py`, `test_webhooks_api_critical_paths.py` etc.), não uma integração real.
- A GitLab Edition estava **17 dias defasada** em relação ao `main` (parada em 2026-06-25, enquanto o projeto avançou com cofre de segredos, Teams Messaging Gateway, Alembic etc.).
- A maioria dos jobs críticos era **placeholder**: `secret_detection_placeholder`, `dependency_container_scanning_placeholder` e `deploy_staging_placeholder` apenas escreviam `echo "...placeholder_ready"` em arquivos de evidência, sem executar nenhuma ferramenta real. O smoke test de runtime (`runtime_backend_smoke`) nem rodava a suíte de testes do backend — só compilava os scripts da própria pasta `gitlab/`.
- O validador de governança (`gitlab/scripts/validate_gitlab_governance.py`) reportava `Status: passed`, mas ele só confere presença de arquivos e palavras-chave — não é evidência de paridade funcional com o pipeline GitHub.

## Decisão

1. **Manter a GitLab Edition como scaffolding local, não como linha de CI ativa.** A linha de CI de produção do ReqSys continua sendo exclusivamente o GitHub Actions. Nenhuma sessão futura deve assumir que pipelines GitLab estão rodando de fato — não há runner, não há projeto GitLab, não há segredos configurados.
2. **Fortalecer os jobs locais para que, no dia em que um projeto GitLab real for provisionado, o pipeline já funcione de verdade**, em vez de continuar como esqueleto de placeholders:
   - `gitlab/ci/runtime.yml` → `runtime_backend_smoke` agora sobe Postgres como `service` e roda a suíte real (`pytest tests/ --cov=app --cov-fail-under=60`), mesmos env vars usados no `backend-test` do GitHub Actions.
   - `gitlab/ci/security.yml` → adicionado `backend_sast_bandit` (SAST real via `bandit`), mantendo `security_baseline_smoke` como marcador leve.
   - `gitlab/ci/devsecops.yml` → placeholders substituídos por ferramentas reais:
     - `secret_detection_gitleaks` (Gitleaks, com `--redact` para não vazar segredo em log/artefato, alinhado ao ADR-002 global de LGPD/PII do usuário),
     - `backend_dependency_scanning_pip_audit` (pip-audit sobre `requirements-audit.txt`),
     - `frontend_dependency_scanning_npm_audit` (npm audit `--audit-level=high`),
     - `container_scanning_trivy` (Trivy `fs` sobre `backend/` e `frontend/`, hoje **não bloqueante** — `--exit-code 0` — porque ainda não há registry de imagem nem política de severidade aprovada; ficará bloqueante quando isso for decidido).
   - `gitlab/ci/deploy.yml` → `deploy_staging_fly` substitui o placeholder: instala `flyctl` de verdade e roda `flyctl deploy --remote-only`. Se `FLY_API_TOKEN` não estiver configurado nas variáveis de CI do projeto GitLab, o job **falha explicitamente** com instrução do que configurar, em vez de fingir sucesso.
   - `gitlab/scripts/validate_gitlab_governance.py` atualizado para exigir os novos nomes de job reais (não mais os placeholders antigos), assim drift futuro (alguém remover a ferramenta real e voltar a um placeholder) é pego pelo próprio gate de governança.
3. **Não foi feita paridade completa com os ~160 workflows do GitHub Actions.** A maior parte deles é automação operacional específica do GitHub (dashboards, product intelligence, auto-remediação, etc.), não gates de qualidade que bloqueiam merge. Foi priorizado trazer paridade nos gates essenciais: testes de backend, lint/SAST, dependency/secret/container scanning e deploy. Review apps por MR (`gitlab/ci/environments.yml`) permanecem como placeholder documentado — dependem de infraestrutura de ambiente efêmero que só faz sentido configurar quando (e se) houver um projeto GitLab real.

## Consequências

- Positivo: se/quando a organização decidir migrar ou espelhar para GitLab, o pipeline não precisa ser escrito do zero — só requer provisionar o projeto, configurar variáveis de CI (`FLY_API_TOKEN`, etc.) e revisar a política de bloqueio do Trivy.
- Positivo: nenhuma sessão futura deve mais confundir a GitLab Edition com uma segunda linha de CI ativa — este ADR e a seção "Status atual" em `gitlab/docs/GITLAB_OPERATING_MODEL.md` deixam isso explícito.
- Trade-off: os novos jobs (`gitlab/ci/*.yml`) nunca foram executados em um runner GitLab real — foram validados por lint YAML (`yaml.safe_load`) e pelo gate de governança local, não por uma pipeline GitLab de verdade. A primeira execução real pode expor ajustes de sintaxe/imagem.
- Trade-off: `container_scanning_trivy` não bloqueia merge hoje (`--exit-code 0`) — é evidência, não gate. Deve virar gate quando a política de severidade for definida.

## Critérios de aceite

- [x] `gitlab/scripts/validate_gitlab_governance.py` reporta `Status: passed` após as mudanças.
- [x] Todos os YAML em `gitlab/ci/*.yml` e `.gitlab-ci.yml` são sintaticamente válidos (`yaml.safe_load`).
- [ ] Execução real em um projeto GitLab (pendente — depende de provisionamento externo, fora do escopo deste ADR).
