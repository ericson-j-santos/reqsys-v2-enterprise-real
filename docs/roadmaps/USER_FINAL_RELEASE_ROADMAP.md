# Roadmap por PRs Pequenos — Liberação do ReqSys para Usuário Final

## Objetivo

Organizar a liberação do ReqSys para usuário final em incrementos pequenos, revisáveis e rastreáveis, reduzindo conflito com PRs abertos e evitando declarar maturidade sem evidência real.

## Decisão arquitetural

A liberação deve ocorrer por fatias verticais pequenas, cada uma com escopo claro, critério de aceite e validação objetiva. A ordem recomendada prioriza primeiro a entrada do usuário, depois operação funcional, analytics, governança e hardening de produção.

## Fases

| Fase | Janela média | Resultado esperado |
|---|---:|---|
| Fase 1 — MVP controlado | 2 a 4 semanas | Usuário final acessa, navega, cria/consulta requisitos e visualiza status básico. |
| Fase 2 — Beta operacional | 4 a 8 semanas | Operação com analytics, auditoria, logs, drill-down e indicadores vivos. |
| Fase 3 — Produção padrão ouro | 8 a 12 semanas | Uso corporativo amplo com segurança, RBAC, observabilidade, gates e ambientes segregados. |

## Sequência de PRs pequenos

### PR-001 — Shell de produto e navegação

**Objetivo:** consolidar a experiência mínima navegável para usuário final.

**Escopo:**

- Layout base responsivo.
- Menu principal com rotas finais.
- Estados de loading, vazio, erro e sucesso.
- Página inicial com status operacional e caminho de uso.

**Critérios de aceite:**

- Usuário identifica onde iniciar.
- Rotas principais não quebram.
- Navegação funciona em desktop e mobile.

### PR-002 — Autenticação e sessão mínima governada

**Objetivo:** permitir acesso controlado sem expor áreas sensíveis.

**Escopo:**

- Login funcional.
- Persistência segura de sessão.
- Guards de rota.
- Tratamento de sessão expirada.

**Critérios de aceite:**

- Rotas privadas bloqueiam acesso anônimo.
- Logout remove sessão local.
- Falhas de autenticação exibem mensagem clara.

### PR-003 — Workspace operacional

**Objetivo:** criar área principal de trabalho do usuário final.

**Escopo:**

- Dashboard operacional básico.
- Lista de requisitos/demandas.
- Ações principais visíveis.
- Cards de status.

**Critérios de aceite:**

- Usuário consegue visualizar o estado do trabalho.
- Cards possuem semântica de status.
- Dados ausentes não quebram a tela.

### PR-004 — Catálogo de requisitos com persistência governada

**Objetivo:** permitir criação, consulta e rastreabilidade básica de requisitos.

**Escopo:**

- Cadastro/edição de requisito.
- Consulta/listagem.
- Identificador rastreável.
- Validações mínimas.

**Critérios de aceite:**

- Requisito criado pode ser consultado.
- Campos obrigatórios são validados.
- Operações geram `correlation_id` quando aplicável.

### PR-005 — Demo guiada e onboarding visual

**Objetivo:** reduzir fricção de uso para usuário não técnico.

**Escopo:**

- Fluxo guiado de primeira utilização.
- Exemplos demonstrativos.
- Ajuda contextual.
- Página de orientação rápida.

**Critérios de aceite:**

- Usuário entende o fluxo sem documentação externa.
- Demo não depende de credenciais sensíveis.

### PR-006 — Dashboard executivo com drill-down

**Objetivo:** evoluir a camada analítica para decisão operacional.

**Escopo:**

- Indicadores executivos.
- Cards clicáveis.
- Drill-down filtrado.
- Semáforo operacional.

**Critérios de aceite:**

- Cada indicador crítico possui explicação e detalhe.
- Drill-down preserva contexto/filtro.

### PR-007 — Runtime-to-analytics e auditoria

**Objetivo:** conectar execução real a indicadores e trilhas auditáveis.

**Escopo:**

- Eventos operacionais.
- Timeline por `correlation_id`.
- Logs sem PII sensível.
- Métricas mínimas de uso e erro.

**Critérios de aceite:**

- Falhas críticas aparecem no painel.
- Eventos são rastreáveis ponta a ponta.

### PR-008 — Segregação DEV/HML/PRD

**Objetivo:** deixar explícito o ambiente de execução e os bloqueios por ambiente.

**Escopo:**

- Banner/indicador de ambiente.
- Configuração segregada.
- Bloqueios de produção.
- Documentação de variáveis.

**Critérios de aceite:**

- Usuário técnico identifica o ambiente.
- Produção não aceita configuração insegura.

### PR-009 — Readiness gates e testes E2E

**Objetivo:** impedir promoção sem validação mínima automatizada.

**Escopo:**

- Testes E2E do fluxo principal.
- Checklist de readiness.
- Gate de segurança/configuração.
- Evidência em CI.

**Critérios de aceite:**

- CI falha se o fluxo principal quebrar.
- Critérios de produção ficam versionados.

### PR-010 — Hardening final de produção

**Objetivo:** preparar liberação corporativa mais ampla.

**Escopo:**

- RBAC consolidado.
- Observabilidade ampliada.
- Performance básica.
- Documentação viva.
- Runbook de operação.

**Critérios de aceite:**

- Operação possui plano de diagnóstico.
- Segurança mínima está validada.
- Usuário final acessa fluxo principal com estabilidade.

## Ordem recomendada de execução

1. PR-001 a PR-005 para liberar MVP controlado.
2. PR-006 e PR-007 para beta operacional.
3. PR-008 a PR-010 para produção padrão ouro.

## Política de execução

- Um PR deve ter escopo pequeno e objetivo.
- Não misturar frontend, backend, CI e documentação extensa no mesmo PR sem necessidade.
- Todo PR deve declarar: objetivo, escopo, fora do escopo, validação e risco residual.
- Não declarar pronto para usuário final sem evidência de acesso, navegação e fluxo principal validado.

## Indicador de decisão

| Condição | Decisão |
|---|---|
| PR-001 a PR-005 concluídos | Liberar acesso controlado. |
| PR-006 a PR-007 concluídos | Liberar beta operacional. |
| PR-008 a PR-010 concluídos | Avaliar produção padrão ouro. |

## Próximo incremento imediato

Executar o **PR-001 — Shell de produto e navegação**, pois ele reduz o maior gap visível para usuário final: entrada, clareza de navegação, responsividade e experiência inicial.
