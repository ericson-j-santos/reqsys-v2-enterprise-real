# Roadmap de liberação do ReqSys para usuário final

## Objetivo

Organizar a liberação do ReqSys por **capacidades verificáveis**, sem associar maturidade a prazo, contagem de PRs ou implementação isolada.

A fonte de verdade para readiness é a evidência atual do repositório/runtime. Este documento define ordem e critérios; não declara nenhum estágio como concluído por si só.

## Princípios

1. A rota `/` permanece a entrada canônica do trabalho diário enquanto rotas transitórias não forem promovidas por decisão de produto.
2. Liberação depende de evidência no HEAD/runtime atuais, não de status histórico.
3. CI verde é necessário, mas não suficiente: fluxo de usuário, segurança, ambiente e runtime também precisam de evidência.
4. Mudanças devem permanecer pequenas, reversíveis e rastreáveis.
5. DEV, homologação e produção possuem gates distintos; ausência de evidência falha fechado.

## Trilha A — acesso controlado

Capacidades mínimas:

- autenticação e sessão;
- rotas privadas protegidas;
- entrada clara pelo painel canônico;
- navegação principal coerente;
- criação/consulta de requisitos;
- estados de erro, vazio e carregamento;
- responsividade e acessibilidade básicas.

**Gate:** evidência E2E atual do fluxo principal + controles de autenticação/autorização + nenhum bloqueio crítico de segurança.

## Trilha B — operação assistida

Capacidades mínimas:

- painel de projetos e jornada de requisitos;
- rastreabilidade requisito → trabalho → entrega → evidência;
- integrações com estado observável;
- monitoramento operacional;
- auditoria por `correlation_id`;
- recuperação/fallback explicitamente degradados, nunca falso verde.

**Gate:** eventos e readbacks verificáveis, com causa de falha e próximo passo operacional.

## Trilha C — análise e decisão

Capacidades mínimas:

- indicadores com fonte/fórmula;
- drill-down;
- GovBI/Query Intelligence sob contratos governados;
- métricas operacionais ligadas à evidência;
- distinção entre análise estática e dados/runtime reais.

**Gate:** origem e confiança dos indicadores verificáveis e nenhum dado ilustrativo promovido a evidência real.

## Trilha D — promoção governada

Capacidades mínimas:

- ambientes explicitamente identificados;
- configuração segregada;
- branch protection e gates obrigatórios;
- E2E aplicável;
- evidência de runtime;
- políticas de segurança, segredos e autorização;
- rollback/diagnóstico documentados.

**Gate:** promoção somente com evidência do ambiente alvo e política vigente.

## Trilha E — uso corporativo amplo

Capacidades mínimas:

- estabilidade observada ao longo de execuções reais;
- operação e incidentes auditáveis;
- observabilidade suficiente para diagnóstico;
- RBAC/políticas consolidados;
- runbooks vivos;
- riscos residuais aceitos explicitamente.

**Gate:** readiness executivo instrumentado e evidência operacional atual. Não existe promoção automática apenas porque itens anteriores foram implementados.

## Ordem de priorização

1. Corrigir bloqueios que impedem acesso/fluxo principal.
2. Corrigir regressões de segurança e governança.
3. Fechar lacunas de evidência operacional.
4. Melhorar clareza/UX do usuário final.
5. Evoluir analytics e automação somente quando a base estiver estável.

## Relação com os mecanismos atuais

Este roadmap deve ser lido junto com:

- `docs/contracts/instrumented-executive-readiness.md`;
- `governance/reqsys-360/route-responsibilities.json`;
- gates de Pre-PR, CI, segurança, ReqSys 360 e evidência;
- evidência de runtime e E2E do HEAD/ambiente atuais.

## Regra de decisão

Nenhuma trilha é considerada concluída por checkbox histórico, prazo estimado ou número de PR. A decisão é derivada da evidência atual e deve permanecer fail-closed quando essa evidência faltar.
