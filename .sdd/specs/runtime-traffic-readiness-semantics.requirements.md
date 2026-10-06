# Readiness de tráfego separado da maturidade operacional

## Contexto

O endpoint público `/api/runtime/readiness` serve ao roteamento e ao supervisor do runtime. O snapshot de monitoramento também contém achados de maturidade, como auditoria persistente e automação destrutiva ainda bloqueada. Esses domínios precisam permanecer visíveis sem produzir indisponibilidade artificial no DEV.

## Critérios de aceite

1. Em ambientes não produtivos, a política `deploy_gate_relaxed` torna achados do monitoramento operacional não bloqueantes para o readiness de tráfego.
2. Os achados continuam contabilizados em `critical_counts.blocked_items` e não podem ser removidos ou apresentados como capacidades implementadas.
3. A evidência declara `readiness_scope=traffic_serving_dependencies` e quantifica os achados não bloqueantes.
4. Produção permanece estrita: qualquer item bloqueante mantém `ready=false` e `readiness_reason=blocked_items_detected`.
5. O contrato possui testes unitários da tabela de decisão e testes HTTP para DEV e produção.
