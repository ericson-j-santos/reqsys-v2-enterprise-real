# ReqSys 360 — roadmap de coerência funcional

Issue de acompanhamento: #1633.

## Objetivo

Reduzir fragmentação, rotas órfãs, informação duplicada e falso positivo funcional por meio de inventário vivo, responsabilidades canônicas, classificação honesta de evidência e gates automáticos.

## Estado do incremento

Base original: `main` em `c8e13103685f656b8676f4696638b30e495418c5`.

**Implementação das seis fases: concluída.** A conclusão formal da PR continua condicionada ao CI/E2E do SHA corrente. Nenhum item funcional é considerado validado apenas pelo checkbox deste documento.

O ReqSys 360 cruza e governa:

- rotas, aliases, catálogo, subgrupos e destinos internos;
- responsabilidades canônicas e sobreposições intencionais;
- consumidores frontend × contratos backend;
- jornadas e classe de evidência (`real-external`, `integration-local`, `controlled-ui-mock`, `static-contract`);
- casos positivo, negativo, leitura independente e idempotência quando aplicável;
- health/readiness/métricas/analytics, correlação, SHA e ambiente;
- estados de UI inclusive delegados a componentes filhos;
- variantes arquiteturais, serviços, scripts e documentação sem referência detectável;
- baseline determinístico para impedir regressão silenciosa.

## Fases

### Fase 1 — Coerência

- [x] Criar auditor executável no CI.
- [x] Cruzar rota, alias, navegação e destinos internos.
- [x] Bloquear destino interno inexistente.
- [x] Bloquear item oculto por subgrupo.
- [x] Compatibilizar `/requisitos/coleta` com a tela canônica de requisitos.
- [x] Compatibilizar `/notificacoes` com o painel canônico de integrações.
- [x] Tornar Qualidade IA, Recomendações IA e Preparar tarefas alcançáveis.
- [x] Publicar evidência JSON e Markdown por execução.

### Fase 2 — Consolidação

- [x] Inventariar componentes usados por múltiplas rotas.
- [x] Inventariar destinos repetidos no catálogo.
- [x] Medir densidade pelo maior grupo efetivamente renderizado, evitando falso alerta por total bruto.
- [x] Classificar sobreposições como canônicas, transitórias ou intencionais em `route-responsibilities.json`.
- [x] Consolidar Dashboard × Analytics × Monitoramento × Governança por responsabilidade funcional.
- [x] Consolidar Painel de Integrações × Central de Automações por responsabilidade funcional.
- [x] Classificar `/requisitos`, `/pipeline` e `/rastreabilidade` como entradas cruzadas intencionais.
- [x] Classificar `UserFinalShellView` em `/home`, `/workspace` e `/ajuda` como shell transitório intencional.

### Fase 3 — Confiabilidade

- [x] Inventariar cobertura E2E por rota distinguindo referência direta, catálogo e ausência detectável.
- [x] Mapear jornadas como entrada → ação → API → efeito/persistência → leitura independente.
- [x] Confrontar consumidores do frontend com contratos de API quando determinístico.
- [x] Inventariar endpoints backend sem consumidor literal sem classificá-los automaticamente como órfãos.
- [x] Classificar evidência por jornada sem promover mock a integração real.
- [x] Exigir caso positivo e negativo/controle em jornadas mutáveis quando aplicável.
- [x] Exigir leitura independente para efeito mutável.
- [x] Exigir evidência de idempotência quando a jornada declarar idempotência aplicável.
- [x] Registrar limitações explícitas das evidências controladas/localizadas.

### Fase 4 — Operação

- [x] Executar auditor como gate versionado no GitHub Actions.
- [x] Vincular artefato de evidência ao `run_id` e SHA da execução.
- [x] Inventariar endpoints de health, readiness, liveness, metrics, monitoramento e analytics.
- [x] Agrupar sobreposições de observabilidade sem assumir duplicidade funcional automaticamente.
- [x] Mapear uso de `correlation_id` em frontend, backend, runtime e serviços.
- [x] Inventariar observabilidade sem vínculo estático detectável a correlação, SHA ou ambiente.
- [x] Manter responsabilidade operacional detalhada em `/monitoramento-operacional` e política/evidência em `/governanca`.

### Fase 5 — Experiência

- [x] Validar alcançabilidade dos itens do catálogo com subgrupos.
- [x] Revisar e reduzir densidade efetiva de Administração por subgrupos.
- [x] Consolidar Analytics como síntese, direcionando operação detalhada a Monitoramento.
- [x] Integrar linguagem simples, acessibilidade, design system e build ao gate ReqSys 360.
- [x] Inventariar estados de carregamento, erro, vazio, bloqueio e offline em páginas dinâmicas.
- [x] Inspecionar estados delegados a componentes locais para evitar falso positivo em wrappers.
- [x] Isentar página realmente estática da obrigação artificial de loading/erro.
- [x] Executar E2E focado da navegação ReqSys 360 no próprio gate dedicado.

### Fase 6 — Higiene

- [x] Inventariar marcadores explícitos de dívida apenas em comentários.
- [x] Impedir falsos positivos com palavras como `todo`, `Método`, prop `placeholder` e modo `mock`.
- [x] Inventariar componentes, serviços e variantes arquiteturais potencialmente legados/experimentais.
- [x] Classificar variantes arquiteturais conhecidas em governança.
- [x] Identificar scripts e documentação sem referência detectável, como inventário não bloqueante.
- [x] Versionar baseline determinístico de regressão.
- [x] Bloquear desaparecimento de métrica governada ou aumento além do limite aprovado.
- [x] Publicar resultado da guarda com `run_id`, SHA, baseline e métricas observadas.
- [x] Preservar artefatos por execução para histórico e diagnóstico.

## Controles contra falso positivo

- O auditor possui fixture negativa que injeta rota inexistente e item oculto por subgrupo.
- Fixtures positivas provam aliases e subgrupos válidos.
- Arquivos de teste dentro de `src` não contam como destinos de runtime.
- A densidade considera o grupo renderizado, não o total lógico do tema.
- Cobertura E2E por catálogo não é rotulada como referência direta.
- Mock controlado recebe classe própria e limitação explícita.
- Página estática não recebe alerta de estado dinâmico.
- `TODO/FIXME/HACK/PLACEHOLDER/MOCK` só contam como dívida quando aparecem como anotação explícita em comentário.

## Critério de conclusão formal

A implementação só pode ser declarada concluída na versão corrente quando:

1. o `ReqSys 360 Coherence Gate` terminar verde no SHA atual;
2. os testes negativos do próprio auditor passarem;
3. o E2E focado executar os quatro cenários de navegação, inclusive controle negativo;
4. a guarda de regressão aprovar o relatório real sem relaxar baseline apenas para obter verde;
5. os demais checks obrigatórios da PR estiverem em estado compatível com integração;
6. a PR permanecer mergeável e sem mudança concorrente não reconciliada.

Merge não faz parte deste roadmap e requer autorização humana explícita separada.
