# Readiness Checklist — Usuário Final ReqSys

## Objetivo

Estabelecer critérios objetivos para decidir quando o ReqSys pode ser liberado para usuário final controlado, beta operacional ou produção padrão ouro.

## Status de decisão

| Nível | Critério mínimo | Decisão |
|---|---|---|
| Acesso controlado | Fluxo principal navegável, autenticação mínima e workspace operacional. | Liberável para poucos usuários. |
| Beta operacional | Analytics, auditoria, logs e indicadores vivos. | Liberável para usuários reais com suporte. |
| Produção padrão ouro | Ambientes segregados, RBAC, E2E, gates e runbook. | Liberável para uso corporativo amplo. |

## Checklist por domínio

### 1. Acesso e autenticação

- [ ] Login funcional.
- [ ] Logout funcional.
- [ ] Sessão expirada tratada.
- [ ] Rotas privadas protegidas.
- [ ] Perfil/permissão exibido quando aplicável.

### 2. Navegação e UX

- [ ] Usuário identifica o ponto de entrada.
- [ ] Menu principal cobre as rotas de produto.
- [ ] Telas possuem estados de loading, vazio, erro e sucesso.
- [ ] Layout responsivo validado em desktop e mobile.
- [ ] Mensagens usam linguagem clara para usuário final.

### 3. Workspace operacional

- [ ] Dashboard inicial funcional.
- [ ] Cards de status exibem semântica clara.
- [ ] Lista de requisitos/demandas acessível.
- [ ] Ações principais estão visíveis.
- [ ] Dados ausentes não quebram a interface.

### 4. Catálogo de requisitos

- [ ] Criar requisito.
- [ ] Consultar requisito.
- [ ] Editar requisito quando permitido.
- [ ] Validar campos obrigatórios.
- [ ] Manter identificador rastreável.

### 5. Analytics e drill-down

- [ ] Indicadores executivos exibidos.
- [ ] Cards críticos são clicáveis.
- [ ] Drill-down preserva contexto/filtro.
- [ ] Semáforo operacional documentado.
- [ ] Métricas possuem origem rastreável.

### 6. Auditoria e observabilidade

- [ ] `correlation_id` disponível nos fluxos críticos.
- [ ] Logs não expõem token, senha, CPF, PII ou connection string.
- [ ] Falhas críticas aparecem no painel operacional.
- [ ] Eventos possuem timeline mínima.
- [ ] Runbook orienta diagnóstico.

### 7. Ambientes e deploy

- [ ] Ambiente atual visível: DEV, HML ou PRD.
- [ ] Configuração segregada por ambiente.
- [ ] Produção bloqueada com auth desligada.
- [ ] Produção bloqueada com CORS inseguro.
- [ ] Variáveis críticas documentadas.

### 8. Testes e gates

- [ ] Teste E2E do fluxo principal.
- [ ] Teste de rota protegida.
- [ ] Teste de erro/fallback operacional.
- [ ] CI registra evidência.
- [ ] Gate impede promoção insegura.

## Critério mínimo para o próximo marco

Para liberar **usuário final controlado**, concluir no mínimo:

- PR-001 — Shell de produto e navegação.
- PR-002 — Autenticação e sessão mínima governada.
- PR-003 — Workspace operacional.
- PR-004 — Catálogo de requisitos com persistência governada.
- PR-005 — Demo guiada e onboarding visual.

## Evidência obrigatória antes de declarar pronto

- Link público validado.
- Ambiente identificado.
- Fluxo principal testado.
- CI sem falha bloqueante.
- Registro de riscos residuais.
- Checklist atualizado.

## Risco residual atual

Enquanto este checklist não estiver completo, o ReqSys deve ser tratado como plataforma em evolução e não como produto final amplamente liberado para usuário final.
