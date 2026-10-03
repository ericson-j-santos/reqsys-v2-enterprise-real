# ReqSys — Diretriz Transversal de Padrão Ouro

> Status: obrigatório para novas demandas e evoluções do ReqSys  
> Ambiente-alvo: sempre declarar `dev`, `homologacao` ou `producao` antes de aplicar mudanças  
> Escopo: todas as funções, abas, fluxos, integrações, painéis, layouts, responsividade, analíticos, testes e documentação

## 1. Objetivo

Estabelecer uma regra fixa para que toda demanda do ReqSys seja tratada com padrão ouro, evitando entregas parciais, sem rastreabilidade, sem validação visual, sem testes ou sem clareza de ambiente.

Toda alteração deve considerar:

- Funções e abas existentes.
- Responsividade em desktop, tablet e mobile.
- Layout, usabilidade, estados vazios, erros, carregamento e acessibilidade.
- Capacidade analítica e drill-down sempre que fizer sentido.
- Ambiente de aplicação: desenvolvimento, homologação ou produção.
- Segurança, governança, rastreabilidade, testes, documentação, versionamento e changelog.

## 2. Regra permanente

Nenhuma entrega do ReqSys deve ser considerada pronta sem avaliação explícita dos seguintes pontos:

| Pilar | Exigência mínima |
|---|---|
| Ambiente | Informar onde a mudança está sendo aplicada: `dev`, `homologacao` ou `producao`. |
| GitFlow | Trabalhar em branch dedicada, abrir PR e evitar merge direto na `main`. |
| Funções | Validar impacto em todas as funções afetadas e fluxos relacionados. |
| Abas/Telas | Revisar todas as abas, menus, painéis, formulários e estados visuais afetados. |
| Responsividade | Validar desktop, tablet e mobile, incluindo menus, cards, tabelas e modais. |
| Layout/UI | Garantir hierarquia visual, espaçamento, contraste, alinhamento, textos claros e estados de erro/vazio/loading. |
| Analítico | Tornar indicadores, cards, dashboards e gráficos clicáveis quando fizer sentido, abrindo o analítico já filtrado. |
| Segurança | Validar autenticação, autorização, CORS, secrets, LGPD, logs sem PII e exposição indevida de endpoints. |
| Governança | Usar correlation_id, trilha de auditoria, rastreabilidade de requisito, decisão e evidência. |
| Testes | Aplicar testes unitários, integração, UI/responsividade e smoke/e2e conforme escopo. |
| CI/CD | Garantir que pipelines e quality gates executem antes de merge/publicação. |
| Documentação | Atualizar README, ADRs, documentação funcional/técnica e changelog quando aplicável. |
| Produção | Produção só pode receber mudança aprovada, testada, com rollback e evidência de validação. |

## 3. Checklist obrigatório por demanda

### 3.1 Ambiente

Antes de implementar, registrar:

- Ambiente atual observado.
- Ambiente de destino.
- Risco de impacto em homologação ou produção.
- Configurações sensíveis usadas por ambiente.
- Evidência de que a mudança não está sendo aplicada no ambiente errado.

Modelo:

```md
Ambiente observado: dev | homologacao | producao
Ambiente de aplicação: dev | homologacao | producao
Risco operacional: baixo | medio | alto
Rollback definido: sim | nao
Evidências: prints, logs, link de PR, execução de testes
```

### 3.2 Funções e abas

Para cada alteração, revisar:

- Login/autenticação.
- Home/dashboard.
- Backlog/requisitos.
- Editor/refinamento de requisitos.
- Integrações.
- Planner/Teams.
- GovBI IA/pesquisa.
- Painéis analíticos.
- Histórico/auditoria.
- Configurações/administração.
- Telas de erro, loading, vazio e sem permissão.

Quando uma aba não for afetada, registrar explicitamente: `avaliada sem impacto`.

### 3.3 Responsividade e layout

Validar no mínimo:

| Breakpoint | Objetivo |
|---|---|
| Mobile | Fluxos principais utilizáveis sem quebra horizontal indevida. |
| Tablet | Cards, filtros, tabelas e menus reorganizados corretamente. |
| Desktop | Melhor aproveitamento de espaço, sem desalinhamentos ou excesso visual. |

Critérios:

- Tabelas com overflow controlado ou renderização alternativa em cards.
- Filtros responsivos e recolhíveis quando necessário.
- Modais não devem ultrapassar a viewport.
- Botões de ação devem permanecer acessíveis.
- Estados de carregamento, vazio e erro devem ser visíveis e compreensíveis.
- Componentes críticos devem ser navegáveis por teclado quando aplicável.

### 3.4 Analítico e drill-down

Sempre que houver indicador, card, gráfico, contador, status ou agrupamento, avaliar se ele deve abrir um analítico.

Padrão recomendado:

```txt
Clique no card/gráfico/status
→ abre painel analítico
→ aplica filtros automaticamente
→ mostra lista detalhada
→ permite exportar ou copiar evidência quando aplicável
→ preserva parâmetros na URL quando fizer sentido
```

Exemplos:

| Elemento sintético | Analítico esperado |
|---|---|
| Card de demandas pendentes | Lista filtrada por status pendente. |
| Card de erros de integração | Lista de falhas com payload mascarado, data, origem e correlation_id. |
| Gráfico por status | Drill-down por status selecionado. |
| Indicador de pipeline | Execuções, etapa, erro, duração e responsável. |
| Planner disparado | Histórico de envio, retorno, falhas e reprocessamento. |
| Pesquisa GovBI IA com erro | Consulta, fonte, erro, base usada, tempo e evidência de fallback. |

## 4. Gates obrigatórios para produção

Produção deve ser bloqueada se qualquer condição abaixo ocorrer:

- Autenticação desligada.
- CORS com `*`.
- JWT sem validação real de issuer/audience.
- Consulta com fonte sem retornar fontes.
- Consulta sem base gerando resposta inventada.
- Ingestão sem permissão administrativa.
- Logs com token, senha, CPF, PII ou connection string.
- Auditoria sem `correlation_id`.
- Connector admin exposto.
- Pipeline quebrado ou quality gate ignorado.
- Falta de rollback.
- Mudança visual sem validação mínima de responsividade.

## 5. Definition of Done — Padrão Ouro

Uma demanda só está concluída quando:

- [ ] Ambiente declarado e validado.
- [ ] Branch dedicada criada.
- [ ] PR aberto com escopo, evidências, testes e riscos.
- [ ] Todas as funções/abas afetadas foram avaliadas.
- [ ] Layout e responsividade foram validados.
- [ ] Analíticos/drill-down foram aplicados onde fizer sentido.
- [ ] Segurança e LGPD revisadas.
- [ ] Logs, auditoria e correlation_id preservados.
- [ ] Testes executados e evidenciados.
- [ ] CI concluído com sucesso.
- [ ] README/ADR/changelog atualizados quando aplicável.
- [ ] Rollback definido para mudanças relevantes.
- [ ] Produção não recebeu alteração sem aprovação e evidência.

## 6. Modelo de PR obrigatório

```md
## Resumo

## Ambiente
- Observado:
- Aplicação:
- Impacto em produção:

## Escopo funcional
- Funções afetadas:
- Abas afetadas:
- Integrações afetadas:

## Responsividade e layout
- Desktop:
- Tablet:
- Mobile:
- Evidências:

## Analíticos / drill-down
- Cards clicáveis:
- Gráficos clicáveis:
- Filtros automáticos:
- URLs/estado preservado:

## Segurança e governança
- Auth/RBAC:
- CORS:
- Secrets:
- Logs sem PII:
- correlation_id:

## Testes
- Unitários:
- Integração:
- UI/responsividade:
- Smoke/e2e:
- CI:

## Documentação
- README:
- ADR:
- CHANGELOG:

## Rollback

## Pendências conhecidas
```

## 7. Decisão canônica

A partir desta diretriz, qualquer demanda do ReqSys deve ser conduzida como incremento completo de produto, não apenas como correção pontual de tela ou código.

A entrega ideal deve sempre responder:

1. O que foi alterado?
2. Em qual ambiente?
3. Quais abas e funções foram avaliadas?
4. Quais impactos visuais e responsivos foram tratados?
5. O que virou analítico clicável?
6. Quais testes foram executados?
7. Quais riscos permanecem?
8. Qual evidência comprova que está pronto?
