# ReqSys Control Center — referência estática (2026-11-10)
**Estado: PARCIAL / PRE-OPERACIONAL, sem backend ou deploy.**

Esta pasta guarda a captura de código do painel estático produzido no chat, sem substituir o site existente em `tools/reqsys-control/` nem o validador em `tools/host-readiness-dashboard/`. O HTML é autocontido; abra `index.html` em navegador moderno. Nenhum computador é acessado. O modo dry-run somente exporta intenções JSON, sem comandos, secrets, despacho, merge ou mutação administrativa.

## Governança e integridade
- Issue de aceite e checkpoint: [#3139](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3139)
- Regras: `chatgpt-operational-rules/main@58dcd4200f412a866278027ba9e433439a03f3b3`, v1.6.21
- Base inicial ReqSys: `ea8cc3a26c65fd84f3abf462fa3f1400ed316e05`
- SHA-256 do HTML original: `2d7eecd0338d54bbfbf0cf59313a6fffdde12c57e3b50358ca41c915bafb0202`
- Identidade do Git blob original: `45befd6b78c3f071ddc558520d7dfb4b959e76a5`
- Custo adicional: `R$ 0,00`; custo não comprovado bloqueia operação
- A fila contém quatro referências a issues verificadas em 2026-11-10, mas **não** é projeção atual do TODO Global. Abertura da issue não é autorização.

## Testes
Com Chromium/Playwright já instalados em ambiente isolado, execute `python tests/test_static_preview.py`. Este teste verifica a interface e negativos de autorização: nenhum despacho, nenhuma mutação e nenhum tráfego externo.
O teste passou localmente em 2026-11-10 (Chromium headless). Não valida hosts reais nem CI da branch. Não cria workflow novo.

## Proibições
Não usar HTML público para receber tokens, dados pessoais ou senhas. Não inferir `ready_for_work` de issue, runner ou canário. Não habilitar execução, Gateway ou TODO Global antes de adapter backend com autenticação, RBAC, controle de custo, preflight atual e readback independente. Sem Docker, shell/GUI, reboot, deploy, PR ou merge automáticos.

## Integração pretendida
Veja [INTEGRATION-PLAN.md](INTEGRATION-PLAN.md). Alterar a aplicação canônica só por PR com `READY_FOR_PR` comprovado no HEAD exato; não transpor indiscriminadamente o protótipo para produção.
