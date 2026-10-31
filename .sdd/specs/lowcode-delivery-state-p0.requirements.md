# LowCode Solution Factory — distinção entre blueprint e instalação

Issue #3122. A geração de JSON/ZIP não pode equivaler a despacho nem instalação.

## Requisitos e critérios de aceite
1. `dry_run=false` com plano ALM responde `pending_dispatch`, sem alegar solicitação enviada.
2. `delivery` separa blueprint, despacho, execução e instalação com recibos inicialmente nulos.
3. ZIP de blueprint deve afirmar `importable=false`; verificar ausência de `solution.xml`.
4. Mesmo pedido reaproveita `idempotency_key` e nunca gera despachos duplicados; `correlation_id` identifica cada chamada.
5. `dry_run=true` mantém `planned`; perfis legados preservados.
6. Entradas inválidas são rejeitadas sem efeito externo.
7. Testes obrigatórios: `backend/tests/test_lowcode_solution_factory.py`, `backend/tests/test_lowcode_teams_notification_profile.py`, Pre-PR e CI no HEAD.
8. E2E DEV futuro: executor ALM real, dispatch com recibo, run confirmado, pacote importável e leitura independente no Power Platform. Até lá, bloqueado.
9. Custo incremental R$ 0,00, sem Docker, deploy ou produção.
