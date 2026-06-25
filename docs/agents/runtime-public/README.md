# REQSYS#002 - IA Runtime Publico / Deploy Runtime

## Identidade operacional

- Frente: `REQSYS#002`
- Agente: `IA_RUNTIME_PUBLICO`
- Dominio: `DEPLOY_RUNTIME`
- Branch padrao: `ai/runtime-public`
- Status inicial: `61%`
- Ambiente alvo: `dev -> staging -> producao`

## Objetivo

Estabilizar a publicacao publica e a operacao runtime do ReqSys v2 Enterprise com deploy governado, health checks, rollback documentado, ambientes rastreaveis e evidencias automatizadas.

## Escopo autorizado

- Publicacao publica.
- Containers e runtime hardening.
- Deploy em dev, staging e producao.
- Healthcheck, readiness, liveness e startup health.
- Rollout e rollback.
- Environments e variaveis nao sensiveis.
- DNS e documentacao operacional.
- Evidencias de deploy e runtime.

## Fora de escopo

- Alterar secrets diretamente.
- Relaxar gates de producao.
- Desabilitar autenticacao em producao.
- Abrir CORS com `*` em producao.
- Alterar workflows de governanca sem validacao da frente REQSYS#005.
- Executar acoes destrutivas sem aprovacao humana e auditoria.

## KPIs

| KPI | Definicao | Estado inicial |
|---|---|---:|
| Uptime | Disponibilidade do endpoint publico | pendente de medicao continua |
| Deploy success rate | Percentual de deploys concluidos sem rollback | pendente de pipeline dedicado |
| MTTR | Tempo medio de recuperacao | pendente de historico |
| Startup health | Validacao de liveness/readiness apos deploy | parcialmente implementado |
| Rollback readiness | Capacidade documentada/testada de rollback | pendente |

## Definition of Done

Um incremento desta frente somente pode ser considerado pronto quando:

1. O PR modifica escopo pequeno e rastreavel.
2. Todos os workflows obrigatorios ficam verdes ou com skip justificado.
3. Nao ha relaxamento de seguranca, CORS, auth, JWT ou gates.
4. Os endpoints de runtime sao validados em ambiente aplicavel.
5. Ha evidencia documental do rollout/rollback quando houver mudanca de deploy.
6. O estado atual evidenciado e diferenciado do estado alvo.

## Primeiro incremento recomendado

Criar a matriz governada de ambientes e rollback:

- `dev`
- `staging`
- `production`

Entregaveis sugeridos:

- documento de estrategia de ambientes;
- checklist de pre-deploy;
- checklist de post-deploy;
- criterios de rollback;
- tabela de URLs e endpoints esperados sem expor secrets.

## Integracoes com outras IAs

| Frente | Integracao |
|---|---|
| REQSYS#001 Coordenadora | aprova merge e prioridade |
| REQSYS#003 Observabilidade | consome health, metrics e uptime |
| REQSYS#004 UX/UI | exibe estado runtime em dashboard navegavel |
| REQSYS#005 Governanca CI | valida gates e workflows |
| REQSYS#006 Automacao Autonoma | usa sinais de runtime para remediacao assistida |
| REQSYS#007 Docs Vivas | versiona arquitetura runtime e runbooks |

## Estado atual evidenciado

- PR #273 mergeado com endpoints de runtime observability.
- Branch `ai/runtime-public` criada para incrementos especificos de deploy publico.
- Proximo bloqueio tecnico: validar exposicao real dos endpoints runtime no ambiente publico e formalizar matriz de ambientes.
