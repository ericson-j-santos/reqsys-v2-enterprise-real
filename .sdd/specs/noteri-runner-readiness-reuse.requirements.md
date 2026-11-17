# Requisitos — Pré-verificação autenticada do runner Noteri

## Objetivo

Reaproveitar o fluxo `Self-Hosted Runner Governance Guard` do ReqSys para consultar, antes de uma possível execução física no Noteri, o status observado do runner registrado no repositório `ericson-j-santos/noteri-runtime`. A consulta deve funcionar sem serviço, credencial, runner ou cobrança adicional e não pode disparar jobs físicos.

## Requisitos funcionais

1. Reutilizar o workflow existente, em job GitHub-hosted distinto do monitor portátil de leases. Aceitar somente `workflow_dispatch` manual do proprietário no modo tipado `noteri-runner-readiness`, na `main` do ReqSys. Não executar essa consulta na agenda enquanto o acesso do App a `noteri-runtime` estiver não comprovado.
2. Reutilizar exclusivamente as referências já existentes ao GitHub App no mesmo repositório. Emitir token temporário limitado ao repositório `noteri-runtime` e à permissão `administration: read`. Falhar fechado se o App não estiver instalado ou autorizado nesse repositório; não criar ou ampliar credenciais automaticamente.
3. Ler exclusivamente as APIs GitHub para o estado de `main` e o cadastro completo e paginado de runners do repositório Noteri; não usar comandos remotos, Desktop Commander como terminal ou endpoints que alterem runners.
4. Verificar exatamente um runner registrado com nome `Noteri-runtime`, `os=Windows`, status `online`, `busy=false` e etiquetas `self-hosted`, `Windows`, `X64`, `noteri` e `reqsys-dev`.
5. Classificar `available_at_observation`, `busy`, `offline` e `label_mismatch`; para resposta inválida, incompleta, duplicada, não autenticada ou sem permissões, bloquear. Nunca interpretar dados antigos, heartbeat da máquina ou CI verde como disponibilidade operacional.
6. Produzir recibo sanitizado com SHA do controle, SHA observado da main do Noteri, GitHub `run_id`, tentativa, horário, nome/ID do runner, estado, razão de não admissão e sinalizadores invariavelmente falsos para `dispatch_executed` e `authorization_for_host`.
7. Preservar integralmente o comportamento do monitor portátil existente. Este continua usando `github.token`, consulta de jobs da própria execução e nunca requer administração; não alterar suas permissões nem testes.
8. Preservar a agenda já configurada exclusivamente para o monitor portátil preexistente, sem adicionar consulta automática de App ainda não validado nem criar workflow, endpoint, serviço ou monitor adicional. O modo manual `noteri-runner-readiness` deve impedir que os jobs antigos `probe-pool` e `monitor-pool` sejam enfileirados. Não publicar inventário bruto nem token, não adquirir lease, não chamar Qwen/Builder e não instalar ou disparar o Noteri. Custo adicional máximo R$ 0,00.

## Critérios de aceite

- O mesmo script, em teste independente, aprova somente uma observação íntegra e bloqueia offline, busy, labels divergentes, os distinto, runner não encontrado, duplicatas, contagem/paginação incompleta, identidade/SHA inválidos e replay sem mutação.
- A CI do ReqSys executa os testes novos e os testes existentes do monitor portátil, inclusive o negativo que impede ampliar a permissão administrativa do monitor antigo.
- Um teste de regressão comprova que executar `noteri-runner-readiness` não agenda `probe-pool` nem `monitor-pool` e que o job novo não é chamado por `schedule`.
- O job de consulta utiliza o GitHub App com `administration: read`, está isolado por condições de evento/branch/repositório, sem chamada de dispatch, mudança de credenciais, `PUT`, `POST` ou upload do inventário.
- Os testes de especificação, pré-PR, YAML, segurança e regressão devem passar no SHA final; até lá `READY_FOR_PR=false`.
- A prova de acesso ao GitHub App instalado em `noteri-runtime` e a execução operacional são pendências posteriores. `available_at_observation` nunca substitui nova autorização física, reserva/lease, Gateway, sessão ou teste de custo do host.