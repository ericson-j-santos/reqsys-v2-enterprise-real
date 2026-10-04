# PDR-<DOMINIO>-<NNN> — <Título>

Version: 0.1.0
Status: draft
Owner: <papel ou equipe>
Last updated: YYYY-MM-DD

## Objetivo

Descrever o resultado operacional esperado deste prompt.

## Aplicabilidade

- Tipo de tarefa:
- Domínio:
- Risco padrão: baixo | médio | alto | crítico
- Ferramentas permitidas:
- Ferramentas proibidas:

## ADRs

### Obrigatórios

- ADR-NNN — motivo

### Relacionados

- ADR-NNN — motivo

## Entradas

### Obrigatórias

| Campo | Tipo | Regra |
| --- | --- | --- |
| objetivo | string | Resultado esperado, sem ambiguidade |
| contexto | object | Somente contexto necessário |

### Opcionais

| Campo | Tipo | Regra |
| --- | --- | --- |
| restricoes | array | Limites adicionais |

## Pré-condições

- estado do repositório ou ambiente validado;
- permissões disponíveis;
- dependências conhecidas;
- ausência de segredos no contexto.

## Guardrails

- preservar trabalho existente;
- aplicar a menor mudança correta;
- não inventar estado, resultado ou evidência;
- não declarar sucesso com CI pendente ou falho;
- mascarar PII e nunca registrar segredos;
- interromper ou escalar quando ADRs entrarem em conflito.

## Sequência de execução

1. Validar contexto e estado real.
2. Identificar causa raiz ou lacuna.
3. Definir plano de alteração.
4. Implementar mudança mínima.
5. Executar validações.
6. Coletar evidências.
7. Registrar riscos, pendências e próximo incremento.

## Contrato de saída

A resposta ou manifesto deve conter:

- estado evidenciado;
- causa raiz ou decisão;
- arquivos e contratos alterados;
- validações executadas;
- links ou identificadores de evidência;
- riscos e bloqueios;
- próximo passo objetivo.

## Critérios de aceite

- [ ] objetivo atendido;
- [ ] ADRs respeitados;
- [ ] testes relevantes executados;
- [ ] segurança e privacidade validadas;
- [ ] evidências registradas;
- [ ] rollback ou recuperação definidos quando aplicável.

## Estratégia de falha e escalonamento

Definir condições que exigem:

- nova tentativa;
- revisão humana;
- abertura de issue;
- proposta de ADR;
- rollback;
- interrupção segura.

## Evidências

| Evidência | Obrigatória | Local esperado |
| --- | --- | --- |
| diff/commit | sim | Git |
| testes | sim | CI ou execução local registrada |
| PR/checks | quando aplicável | GitHub/GitLab |
| runtime | quando aplicável | logs, healthcheck ou dashboard |

## Changelog

### 0.1.0 — YYYY-MM-DD

- versão inicial.
