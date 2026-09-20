# RSM-05 — Tela única do ServiceCase com ações governadas — Requisitos

Issue: #1787
Parent: #1782
Depende de: RSM-01 (#1783), RSM-02 (#1784), RSM-03 (#1785), RSM-04 (#1786)
Desbloqueia: RSM-06 (#1788), RSM-07 (#1789)

## Requisito 1 — uma única tela para os quatro tipos
A mesma tela operacional deve carregar e apresentar `REQUEST`, `INCIDENT`, `PROBLEM` e `CHANGE`. Não criar telas paralelas nem regras de estado específicas por tipo no frontend.

## Requisito 2 — backend como fonte autoritativa de ações
A UI não deve reproduzir a máquina de estados do domínio. `GET /v1/service-cases/{case_id}` deve retornar `allowed_transitions` derivado de `ServiceCase.allowed_transitions()`, e a tela deve renderizar somente essa lista como ações navegáveis.

## Requisito 3 — concorrência otimista preservada
Toda transição enviada pela UI deve usar a `version` observada no caso persistido. Versão obsoleta deve continuar sendo rejeitada pelo backend com conflito, sem atualização visual otimista.

## Requisito 4 — sucesso somente após leitura independente
Depois de uma mutação, a UI deve executar nova leitura de `/v1/service-cases/{case_id}` e `/v1/service-cases/{case_id}/operations`. A tela só apresenta sucesso se a leitura posterior observar o estado alvo persistido e a mesma identidade do caso.

## Requisito 5 — erro fail-closed
HTTP 4xx/5xx, identidade divergente, estado divergente após POST ou falha da releitura devem aparecer como erro. A tela não pode manter falso sucesso nem avançar estado apenas localmente.

## Requisito 6 — resolução exige evidência objetiva
A ação `RESOLVED` deve exigir `evidence_uri` não vazia e SHA-256 hexadecimal de 64 caracteres antes do POST, preservando a validação autoritativa do backend.

## Requisito 7 — contexto operacional visível
A mesma tela deve mostrar estado, tipo, prioridade, versão, serviço, solicitante, origem, `correlation_id`, atribuição atual, estado de SLA, quantidade de aprovações e histórico auditável.

## Requisito 8 — navegação e responsividade
A tela deve ser acessível em `/service-cases/:caseId?`, aparecer na navegação de trabalho e fazer parte da matriz responsiva oficial sem quebrar as rotas existentes.

## Critérios de aceite (Acceptance Criteria)
1. Caso `NEW` retorna ações exatamente derivadas do domínio; `CLOSED` retorna lista vazia.
2. Frontend rejeita UUID inválido antes de chamar a API.
3. Carregamento exige que caso e operações retornem o mesmo `case_id`.
4. Transição usa a versão persistida atual e um `event_id` novo.
5. Resolução sem URI/SHA-256 não envia mutação.
6. POST sem confirmação do estado alvo por GET posterior é tratado como falha.
7. Erro do backend não gera atualização visual otimista.
8. Uma única rota atende os quatro tipos de `ServiceCase`.
9. Build e testes frontend passam no HEAD exato.
10. Testes backend direcionados passam no HEAD exato.
11. E2E de interface deve exercitar ao menos um `REQUEST` real: carregar -> transicionar -> reler persistência -> controle negativo sem alteração -> replay sem efeito adicional.
12. O E2E deve registrar ambiente, branch/SHA, `correlation_id`, entrada, esperado e observado.
13. Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato antes da abertura da PR.
