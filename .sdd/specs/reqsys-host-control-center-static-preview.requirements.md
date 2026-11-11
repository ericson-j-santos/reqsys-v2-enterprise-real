# ReqSys Host Control Center — referência estática

## Objetivo
Versionar, em pasta isolada, a interface HTML autocontida de planejamento governado, preservando os módulos canônicos `tools/reqsys-control` e `tools/host-readiness-dashboard`.

## Requisitos
1. O código deve permanecer em `tools/reqsys-control/prototypes/host-control-center-20261110/`, sem substituir a aplicação operacional.
2. Exibir fila Pareto e os quatro hosts, mantendo `ready_for_work=false` enquanto não houver atestado independente autenticado.
3. Toda intenção produzida pelo frontend deve ser de preparação ou dry-run; nunca despachar, acessar Gateway, inserir secrets ou executar mutações administrativas.
4. Reproduzir bloqueios de custo desconhecido, falta de preflight, ausência de lease ou autorização em vez de permitir ações.
5. Registrar referência à issue #3139, origem do HTML, SHA de regras e limitações de evidência e E2E.
6. Não criar novo workflow GitHub, Docker, recurso pago ou integração paralela ao TODO Global.

## Critérios de aceite (Acceptance Criteria)
1. A página é renderizada em Chromium local e a fila apresenta quatro referências; isso não certifica que as issues ainda estejam abertas.
2. Os quatro cartões de hosts mostram `ready_for_work=false`, mesmo após importação local não autenticada.
3. Botões de execução real estão desabilitados e o preflight retorna `Bloqueado`.
4. A geração de intenções não emite chamadas externas nem alteração administrativa.
5. O teste `tests/test_static_preview.py` existente na pasta do protótipo passa no ambiente local isolado.
6. `scripts/sdd_gate.py` reconhece esta especificação no diff; Pre-PR só será declarado aprovado após novo run verde, sem skipped/neutral obrigatórios.
7. Publicação no GitHub não é publicação em Pages; E2E físico, Gateway e TODO Global continuam bloqueados até validação de fonte independente e autorização separada.
