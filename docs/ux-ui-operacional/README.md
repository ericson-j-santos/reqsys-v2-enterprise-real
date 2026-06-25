# REQSYS#004 — UX/UI Operacional

Atualizado em: 2026-06-25  
Branch padrão: `ai/ux-operacional`  
Estado alvo informado: 67%  
Estado evidenciado neste incremento: implementação P0 de drill-down navegável na aba `/estatisticas`

## Objetivo

Consolidar a experiência operacional do ReqSys com foco em:

- responsividade;
- dashboards;
- navegação;
- drill-down;
- analytics navegável;
- UX operacional;
- schema-driven UI.

## Escopo do incremento P0

Este incremento transforma um gap documentado da aba Estatísticas em entrega funcional:

- adiciona contrato de drill-down por indicador em `frontend/src/services/estatisticas.js`;
- expõe abertura de drill-down por card e por linha da tabela em `frontend/src/views/EstatisticasView.vue`;
- preserva fonte, fórmula, evidências, pendências, guard rails e trilha de auditoria;
- adiciona testes unitários para o contrato navegável;
- atualiza a documentação de UI/UX.

## DoD — Definition of Done

- [x] Mudança pequena e limitada à frente UX/UI.
- [x] Sem alteração de ambiente produtivo.
- [x] Sem criação de fonte externa fictícia.
- [x] Estado atual não promovido para estado alvo sem evidência.
- [x] Drill-down acessível por botão e teclado.
- [x] Testes unitários adicionados para contrato de drill-down.
- [ ] CI validado no PR.
- [ ] Navegação pública validada após CI verde.

## KPIs de acompanhamento

| KPI | Medição P0 | Critério de evolução |
|---|---:|---|
| Responsividade | Layout já usa grid e media queries | Validar em viewport mobile/tablet/desktop |
| Navegação operacional | Drill-down por card e tabela | Evoluir para rotas dedicadas por indicador |
| Acessibilidade | `aria-label`, foco e teclado | Adicionar teste E2E acessível |
| Usabilidade | Próxima ação explícita | Medir tempo até chegar ao detalhe analítico |
| Rastreabilidade | Trilha indicador/fonte/estado | Linkar evidências versionadas |

## Próximo incremento recomendado

`REQSYS#004.P1 — Operational Analytics Navigation Routes`

- criar rota navegável por indicador, por exemplo `/estatisticas/:indicadorId`;
- permitir deep link para evidência, fonte e guard rail;
- registrar analytics de navegação com `correlation_id`;
- adicionar teste E2E de acesso público controlado.

## Limites operacionais

- Não executar merge sem CI verde.
- Não publicar link como concluído sem validação pública.
- Não declarar maturidade avançada sem evidências reais.
- Não misturar esta frente com runtime/deploy, observabilidade ou automação autônoma.
