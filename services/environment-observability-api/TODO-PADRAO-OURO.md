# TODO — Environment Observability API até Padrão Ouro 100%

Atualizado em: 2026-07-14

## Regra de configuração

O `fly.toml` da raiz pertence à API principal `reqsys-api` e não deve ser reutilizado por este serviço. O módulo usa exclusivamente:

- `fly.dev.toml` → `reqsys-env-api-dev.fly.dev`;
- `fly.stg.toml` → `reqsys-env-api-stg.fly.dev`;
- `fly.prod.toml` → `reqsys-env-api-prod.fly.dev`.

Cada contrato deve manter `APP_ENV`, `PUBLIC_ENVIRONMENT` e `API_PUBLIC_URL` coerentes com o próprio aplicativo Fly.io.

## Estado evidenciado atual

| Dimensão | Atual | Meta | Condição para 100% |
|---|---:|---:|---|
| Infraestrutura e governança geral | 85% | 100% | pipeline de promoção, approvals, rollback e evidência imutável |
| Segregação efetiva por ambiente | 45% | 100% | apps, secrets, storage, DNS e telemetria fisicamente separados |
| Padronização de logs | 75% | 100% | schema versionado, masking testado, OpenTelemetry e retenção |
| Serviço reutilizável | 85% | 100% | SDK/clientes, autenticação opcional, contrato estável e exemplos integrados |
| Provisionamento operacional real | 35% | 100% | deploy real DEV/STG/PROD e smoke público verde |
| Padrão ouro consolidado | 65% | 100% | SLO comprovado, incidentes, dashboards e janela de estabilidade |

## P0 — Bloqueios para uso produtivo

- [ ] Criar os aplicativos Fly.io `reqsys-env-api-dev`, `reqsys-env-api-stg` e `reqsys-env-api-prod`.
- [ ] Configurar `FLY_API_TOKEN` por GitHub Environment, sem token compartilhado entre produção e não produção.
- [ ] Criar GitHub Environments `development`, `staging` e `production`.
- [ ] Exigir aprovação humana no environment `production`; não criar bypass por código.
- [ ] Publicar a mesma imagem/digest em DEV → STG → PROD, sem rebuild entre ambientes.
- [ ] Executar smoke público em `/health`, `/api/runtime/health`, `/api/runtime/readiness`, `/api/runtime/liveness` e `/api/v1/environment`.
- [ ] Validar em runtime que `APP_ENV`, `PUBLIC_ENVIRONMENT` e `API_PUBLIC_URL` correspondem ao host acessado.
- [ ] Implementar rollback para o digest anterior e testar a reversão em STG.
- [ ] Publicar artifact JSON contendo ambiente, URL, commit, digest, timestamps, resultados e `correlation_id`.

## P1 — Segregação e segurança

- [ ] Separar secrets, service accounts, volumes, bancos, filas, cache e storage por ambiente.
- [ ] Proibir credenciais de PROD em DEV/STG por gate automatizado.
- [ ] Adicionar CORS allowlist configurável e deny-by-default.
- [ ] Definir autenticação/autorização opcional para endpoints administrativos futuros.
- [ ] Aplicar rate limiting e limites de payload antes de criar endpoint de ingestão de logs.
- [ ] Gerar SBOM e executar scan de imagem/dependências.
- [ ] Assinar ou atestar a imagem publicada e registrar o digest.
- [ ] Adicionar política de lifecycle e atualização de dependências.

## P1 — Logs e observabilidade

- [ ] Versionar o schema de logs (`log_schema_version`).
- [ ] Adicionar `span_id`, `deployment_id`, `region`, `instance_id` e categoria do evento.
- [ ] Validar `traceparent` conforme W3C em vez de apenas dividir a string.
- [ ] Implementar filtro central de redaction para Authorization, cookies, tokens, secrets, CPF, e-mail e telefone.
- [ ] Criar testes negativos que garantam ausência de dados sensíveis nos logs.
- [ ] Integrar OpenTelemetry SDK e Collector para logs, métricas e traces.
- [ ] Publicar métricas RED: taxa, erros e duração.
- [ ] Definir retenção por ambiente e trilha de auditoria protegida.
- [ ] Criar alertas por impacto/SLO e runbooks associados.
- [ ] Detectar perda de telemetria e falha do collector.

## P1 — Reutilização em outras aplicações

- [ ] Publicar OpenAPI versionado e aplicar teste de breaking change.
- [ ] Criar cliente Python reutilizável com timeout, retry, circuit breaker e propagação de correlation ID.
- [ ] Criar exemplo .NET/JavaScript para consumo do contrato HTTP.
- [ ] Disponibilizar Docker Compose de exemplo para integração local.
- [ ] Criar pacote/SDK versionado sem dependência do domínio ReqSys.
- [ ] Definir política SemVer, changelog e janela de depreciação.
- [ ] Adicionar teste de integração de uma aplicação consumidora externa.
- [ ] Documentar limites: este serviço atualmente expõe metadados/health e não é ainda um coletor central de logs.

## P2 — Operação consolidada

- [ ] Dashboard separado por ambiente com disponibilidade, latência, erros e versão implantada.
- [ ] SLO inicial: disponibilidade ≥ 99,9% em PROD e taxa de erro dentro do orçamento.
- [ ] Criar incidentes automáticos quando SLO ou smoke forem violados.
- [ ] Definir RTO, RPO, responsáveis e escalonamento.
- [ ] Testar disaster recovery e restauração de configuração.
- [ ] Coletar janela mínima de estabilidade antes de declarar `gold_certified`.
- [ ] Gerar relatório de maturidade baseado somente em evidências reais.

## Critério de conclusão 100%

A frente somente pode ser declarada padrão ouro quando todos os P0/P1 estiverem concluídos, os três ambientes responderem publicamente com configuração coerente, o pipeline promover o mesmo digest, produção exigir aprovação, rollback estiver testado e houver janela operacional com SLO e telemetria comprovados.
