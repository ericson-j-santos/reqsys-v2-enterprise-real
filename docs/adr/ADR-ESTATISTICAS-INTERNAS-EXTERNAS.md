# ADR — Aba Estatísticas com dados internos e externos auditáveis

Data: 2026-06-21
Status: Aceita como incremento planejado
Contexto: ReqSys v2 Enterprise Real

## Contexto

O ReqSys precisa de uma aba dedicada a estatísticas para uso próprio da solução, acompanhamento da evolução, análise operacional e uso de informações externas como apoio à tomada de decisão.

A solução já possui diretrizes de padrão ouro, governança, rastreabilidade, arquitetura viva, analytics, guard rails e diferenciação obrigatória entre estado atual evidenciado e estado alvo desejado.

## Decisão

Criar uma aba `Estatísticas` composta por dois domínios principais:

1. **Estatísticas internas evidenciadas**
   - requisitos;
   - uso da solução;
   - CI/CD;
   - PRs e releases;
   - segurança;
   - governança;
   - IA/RAG;
   - documentação viva.

2. **Estatísticas externas auditáveis**
   - benchmarks;
   - tendências tecnológicas;
   - indicadores públicos;
   - referências regulatórias;
   - dados de mercado;
   - demais fontes autorizadas.

Todo indicador deverá possuir fonte, fórmula, data de coleta, confiabilidade, estado atual, estado alvo, evidências e pendências.

## Decisões complementares

- Dados externos não entram como verdade absoluta.
- Dados externos devem ser marcados como externos, com TTL e confiabilidade.
- Mocks só podem ser usados em desenvolvimento e devem ser explicitamente identificados.
- Produção deve bloquear indicadores críticos sem fonte ou fórmula.
- A UI deve permitir drill-down analítico por indicador.
- O estado atual não pode ser promovido sem implementação e validação completa.

## Consequências positivas

- Maior visibilidade operacional da solução.
- Base para monitoramento contínuo.
- Rastreabilidade de maturidade real.
- Redução de decisões subjetivas.
- Preparação para dashboards, Power BI, observabilidade e IA explicável.

## Riscos

| Risco | Mitigação |
|---|---|
| Dado externo desatualizado | TTL, data de coleta e status da fonte |
| Indicador promovido sem evidência | guard rail de estado atual evidenciado |
| Mock confundido com dado real | bloqueio de produção para mock real-like |
| Exposição de informação sensível | mascaramento, logs seguros e revisão LGPD |
| Métrica sem utilidade prática | owner, fórmula e decisão associada |

## Critérios de aceite arquitetural

- A aba Estatísticas existe no menu principal.
- Indicadores internos e externos são visualmente diferenciados.
- Cada indicador possui fonte e fórmula.
- Cada indicador permite abrir o analítico.
- Existe validação para bloquear indicador sem fonte/fórmula.
- Existe documentação versionada da decisão.
- Existe changelog do incremento.

## Próximos passos

1. Criar contrato TypeScript dos indicadores.
2. Implementar tela inicial `/estatisticas`.
3. Implementar cards executivos e tabela analítica.
4. Conectar primeiro dados internos versionados.
5. Conectar GitHub Actions/PRs.
6. Adicionar conectores externos com governança.
7. Criar testes unitários, responsivos e de guard rails.
