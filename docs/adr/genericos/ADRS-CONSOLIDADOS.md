# ADRs Consolidados — Pacote Genérico ReqSys

**Data:** 2026-06-22  
**Versão:** 1.0.0  
**Uso:** base reutilizável para decisões de arquitetura, segurança, governança, IA, CI/CD, observabilidade, frontend analítico, integrações e operação autônoma.

---

## ADR-000 — Template de Decisão Arquitetural

**Status:** Proposto

### Decisão

Toda decisão arquitetural relevante deve ser registrada com contexto, problema, opções consideradas, decisão, consequências, critérios de aceite, plano de implementação, evidências e próxima revisão.

### Estrutura mínima

- Contexto.
- Problema.
- Forças e restrições.
- Opções consideradas.
- Decisão.
- Consequências.
- Critérios de aceite.
- Evidências.
- Próxima revisão.

---

## ADR-001 — Arquitetura Hexagonal e Separação por Camadas

**Status:** Aceito

### Decisão

Adotar Arquitetura Hexagonal, também chamada Ports and Adapters, como padrão para módulos críticos.

### Diretrizes

- Domínio sem dependência de banco, HTTP, framework, IA, cloud ou UI.
- Casos de uso dependem de portas, não de implementações concretas.
- Adaptadores externos devem ser substituíveis.
- Regras de negócio devem ser testáveis sem rede e sem banco.
- Integrações externas devem possuir timeout, retry, circuit breaker e logs estruturados.

### Critérios de aceite

- Domínio isolado.
- Portas explícitas.
- Adaptadores com tratamento de erro.
- Testes unitários no domínio.
- Testes de contrato em adaptadores.

---

## ADR-002 — Proteção LGPD, PII, Segredos e Mascaramento

**Status:** Aceito

### Decisão

Adotar política obrigatória de mascaramento de PII, bloqueio de segredos em logs, validação de payloads, segregação de permissões, proteção de prompts/respostas de IA e varredura automatizada em CI/CD.

### Dados protegidos

- CPF.
- E-mail.
- Telefone.
- Nome completo.
- Matrícula.
- Tokens.
- Senhas.
- API keys.
- Connection strings.
- Dados financeiros.
- Prompts e respostas com contexto sensível.

### Critérios de aceite

- Logs sem PII integral.
- Testes de mascaramento.
- CI com validação básica contra vazamento.
- Erros sem stack trace sensível para usuário final.

---

## ADR-003 — Auditoria, Correlação e Rastreabilidade Operacional

**Status:** Aceito

### Decisão

Toda operação relevante deve possuir `correlation_id` propagado entre frontend, backend, APIs internas, filas, logs, auditoria, relatórios, IA e workflows.

### Eventos auditáveis

- Login/logout.
- Consulta inteligente.
- Execução SQL.
- Ação de IA.
- Remediação automática.
- Alteração de configuração.
- Falha de segurança.

### Critérios de aceite

- `correlation_id` criado quando ausente.
- `correlation_id` propagado entre camadas.
- Auditoria persistida para eventos críticos.
- Relatórios exibem correlação.

---

## ADR-004 — Autenticação, JWT e RBAC

**Status:** Aceito

### Decisão

Adotar autenticação baseada em token com validação real de JWT e autorização por papéis/permissões.

### Bloqueios obrigatórios em produção

- Auth desligada.
- JWT sem issuer.
- JWT sem audience.
- Endpoint administrativo público.
- CORS com `*`.
- Bypass inseguro por variável de ambiente.

### Papéis recomendados

- `REQSYS_VIEWER`.
- `REQSYS_ANALYST`.
- `REQSYS_ADMIN`.
- `REQSYS_SECURITY`.
- `REQSYS_RUNTIME_OPERATOR`.
- `REQSYS_AI_GOVERNOR`.

---

## ADR-005 — Segregação de Ambientes e Gates de Produção

**Status:** Aceito

### Decisão

Diferenciar desenvolvimento, homologação e produção com gates bloqueantes no boot, CI/CD e workflows de publicação.

### Gates bloqueantes

- Autenticação desligada.
- CORS com `*`.
- JWT sem issuer/audience.
- Logs com PII ou segredos.
- Consulta inteligente sem fonte.
- IA inventando resposta sem evidência.
- Ingestão sem permissão administrativa.
- Auditoria sem `correlation_id`.
- Debug ativo.
- `verify=False` em TLS.
- Secrets hardcoded.

---

## ADR-006 — CI/CD, Quality Gates e Pull Requests

**Status:** Aceito

### Decisão

Toda mudança relevante deve passar por Pull Request com quality gates mínimos.

### Gates mínimos

- Build.
- Testes unitários.
- Lint.
- Segurança básica.
- Validação de ambiente.
- Changelog.
- ADR quando houver decisão arquitetural.
- Relatório HTML autocontido quando aplicável.

### Regra operacional

PR deve permanecer em draft quando CI não estiver verde, houver conflito, documentação incompleta ou gaps críticos conhecidos.

---

## ADR-007 — Observabilidade, Telemetria e Runtime Health

**Status:** Aceito

### Decisão

Adotar health checks, readiness checks, liveness checks, métricas técnicas e funcionais, logs estruturados, tracing por `correlation_id`, painel operacional e status visual por severidade.

### Checks mínimos

- API.
- Banco.
- Autenticação.
- IA.
- Auditoria.
- Logs.
- Frontend.
- CI/CD.

---

## ADR-008 — IA Governada, RAG, Fontes e Explainability

**Status:** Aceito

### Decisão

Toda capacidade de IA deve ser governada por política de uso, fontes obrigatórias quando depender de conhecimento interno, rastreabilidade, permissão, explainability, confiança, bloqueio anti-alucinação e auditoria sanitizada.

### Regras

- Resposta sem base deve informar ausência de evidência.
- Consulta interna deve retornar fonte.
- Dado sensível deve ser mascarado.
- Ação operacional exige autorização.
- Modelo externo exige política de dados.
- SQL gerado por IA deve ser validado antes de executar.

---

## ADR-009 — Frontend Schema-Driven UI, Analytics e Drill-down

**Status:** Aceito

### Decisão

Adotar Schema-Driven UI e Dynamic Data Renderer para componentes analíticos, quando fizer sentido.

### Regras

Componentes devem ser responsivos, acessíveis, filtráveis, clicáveis, rastreáveis, conectados ao analítico correspondente, consistentes em cores/status, documentados e testáveis.

### Drill-down deve responder

- O que representa?
- Qual período?
- Qual fonte?
- Qual fórmula?
- Quais registros compõem o valor?
- Quem pode visualizar?
- Qual atualização mais recente?

---

## ADR-010 — Integrações, Adapters, Resiliência e Timeouts

**Status:** Aceito

### Decisão

Toda integração deve ser implementada por adapter governado, com contrato explícito, tratamento de erro, timeout, retry, circuit breaker, idempotência, validação de contrato, logs sanitizados, `correlation_id` e TLS verificado.

### Proibições

- Chamada externa direta no domínio.
- Retry infinito.
- Payload sensível integral em log.
- Erro ignorado silenciosamente.
- `verify=False`.
- Escrita sem idempotência quando houver risco de duplicidade.

---

## ADR-011 — Operação Autônoma, Remediação Governada e Guard Rails

**Status:** Proposto

### Decisão

A operação autônoma será adotada de forma progressiva e governada.

### Níveis de autonomia

| Nível | Descrição |
|---|---|
| N0 | Observa apenas |
| N1 | Recomenda ação |
| N2 | Executa ação segura |
| N3 | Executa remediação controlada |
| N4 | Atua em produção com autorização forte |
| N5 | Autonomia plena não permitida inicialmente |

### Guard rails

- Produção exige política específica.
- Escrita em banco exige autorização.
- Alteração em Git exige PR.
- Deploy exige CI verde.
- Remediação repetida deve ser bloqueada.
- Toda ação deve possuir `correlation_id`.

---

## ADR-012 — Documentação Viva, Arquitetura Viva e Relatórios HTML

**Status:** Aceito

### Decisão

Adotar documentação viva como padrão transversal.

### Entregas esperadas

- Markdown versionado.
- ADRs.
- Changelog.
- Diagramas Mermaid.
- Relatório HTML autocontido.
- Evidências de CI.
- Links de PR/workflow.
- Status atual evidenciado.
- Próximos passos objetivos.

### Princípios

Documentação e fluxos devem ser vivos, automáticos, navegáveis, integrados ao runtime, integrados ao código, integrados ao analytics, versionados, auditáveis e explicáveis por IA.
