# ADR-048 — Pool de runners DEV baseado em capacidades

## Status

Proposto para revisão. Nenhum runner ou ambiente foi alterado por esta mudança.

## Contexto

Os fluxos portáveis DEV eram agendados pela label histórica `pc24x7` e parte do código aceitava somente `DESKTOP-PDQK954`. Isso transformava um PC em ponto único de falha e confundia identidade física com autorização operacional.

## Decisão

Os fluxos portáveis usam o pool lógico `reqsys-dev-pc-pool-v1`, com seleção física separada por capacidade: `reqsys-dev-base-v1` para Git/Python, `reqsys-dev-runtime-v1` para Docker e `reqsys-dev-ollama-v1` para Docker/Ollama. Cada job exige apenas a label do seu perfil e executa um preflight local, após o checkout imutável, que valida manifesto, Windows, ferramentas, checkout/origem permitida, runtime root, capacidades e salvaguardas DEV.

As labels são cumulativas no onboarding: um runner `runtime` também pode receber jobs `base`, e um runner `ollama` também pode receber jobs `runtime` e `base`. Um runner `base` nunca recebe jobs que exijam Docker ou Ollama.

O manifesto atribui um `runner_instance_id` opaco. Hostname e `runner_id` do GitHub não participam do agendamento, autorização ou evidência. O runtime root vem do manifesto e é exportado como `REQSYS_DEV_RUNTIME_ROOT`.

O preflight exige `allowed_environments` exatamente igual a `['dev']` e as quatro salvaguardas negativas para HML, STG, PROD e retry automático. A falha de qualquer prova bloqueia o job antes da ação operacional.

Workflows de manutenção de equipamento que realmente têm um Desktop como alvo permanecem fora do contrato portável. Essa exceção não permite que um fluxo DEV portável volte a depender do equipamento.

A adoção é faseada: a primeira entrega cobre o contrato, reconcile, gateway e canário do pool; a segunda migra probes/inventários sintéticos legados; a terceira reduz os workflows de recuperação aos únicos passos realmente host-bound; a quarta realiza onboarding e drenagem físicos sob autorização owner específica.

## Consequências

- um PC novo só entra no pool depois do onboarding e preflight positivo;
- a retirada começa pela remoção da label mais especializada e termina pela label `base`, permitindo drenagem gradual;
- concurrency, environments e autorizações owner existentes permanecem válidos;
- a adoção física das labels e do manifesto é um gate operacional separado e revisável;
- nenhuma promoção ou acesso a HML/STG/PROD é concedido.
