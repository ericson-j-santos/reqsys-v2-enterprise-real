# ReqSys 360 — roadmap de coerência funcional

Issue de acompanhamento: #1633.

## Objetivo

Reduzir fragmentação, rotas órfãs, informação duplicada e falso positivo funcional por meio de um inventário vivo e gates automáticos.

## Estado do incremento inicial

Base: `main` em `c8e13103685f656b8676f4696638b30e495418c5`.

O primeiro incremento cria um auditor estático do frontend que cruza:

- rotas e aliases declarados;
- catálogo e subgrupos de navegação;
- destinos internos encontrados no código;
- reaproveitamento de componentes por múltiplas rotas;
- densidade de itens por tema;
- presença de referência E2E por rota;
- marcadores de higiene (`TODO`, `FIXME`, `HACK`, `PLACEHOLDER`, `MOCK`).

Inconsistências que tornam uma função inacessível ou levam a uma rota inexistente são bloqueantes. Duplicidade, densidade e ausência de referência E2E são inicialmente inventariadas como avisos para permitir migração incremental sem mascarar dívida conhecida.

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
- [x] Detectar excesso de itens no mesmo tema.
- [ ] Classificar cada sobreposição como canônica, alias, legado ou responsabilidade distinta.
- [ ] Consolidar Dashboard × Analytics × Monitoramento × Governança por responsabilidade funcional.
- [ ] Consolidar Painel de Integrações × Central de Automações por responsabilidade funcional.

### Fase 3 — Confiabilidade

- [x] Inventariar rotas sem referência E2E detectável.
- [ ] Mapear tela → ação → API → efeito → leitura independente.
- [ ] Confrontar consumidores do frontend com contratos de API quando determinístico.
- [ ] Classificar E2E real, parcial, mock e ausente por jornada.
- [ ] Exigir caso positivo, negativo/controle e idempotência onde aplicável.

### Fase 4 — Operação

- [x] Executar auditor como gate versionado no GitHub Actions.
- [x] Vincular artefato de evidência ao `run_id` e SHA da execução.
- [ ] Inventariar health checks, métricas e painéis duplicados.
- [ ] Mapear `correlation_id` nas jornadas críticas.
- [ ] Identificar logs/métricas sem fonte canônica ou sem vínculo ao ambiente/SHA.

### Fase 5 — Experiência

- [x] Validar alcançabilidade dos itens do catálogo com subgrupos.
- [x] Detectar densidade excessiva de opções por tema.
- [ ] Revisar nomenclatura e hierarquia das áreas sinalizadas.
- [ ] Integrar resultados dos gates existentes de acessibilidade, linguagem simples e design system ao relatório 360.
- [ ] Inventariar páginas sem estados de carregamento, vazio, erro e bloqueio.

### Fase 6 — Higiene

- [x] Inventariar marcadores explícitos de dívida no frontend.
- [ ] Classificar marcadores encontrados em real, teste, documentação ou falso positivo.
- [ ] Inventariar componentes, serviços e variantes de frontend potencialmente legados/experimentais.
- [ ] Identificar scripts e documentação sem referência atual.
- [ ] Persistir série histórica do relatório para detectar regressão de tendência.

## Critério de conclusão

Nenhuma mudança funcional deve ser considerada concluída somente porque compila ou porque o gate está verde. A evidência funcional continua sujeita às regras de validação ponta a ponta do projeto, com vínculo ao SHA atual, caso positivo, controle negativo quando aplicável e leitura independente do efeito final.
