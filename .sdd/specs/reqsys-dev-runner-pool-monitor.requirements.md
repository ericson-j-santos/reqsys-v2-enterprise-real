# Requisitos — monitor do pool de runners ReqSys DEV

## Objetivo

Detectar periodicamente indisponibilidade e desvio de labels no pool portátil de runners ReqSys DEV, sem depender de um host específico para executar o próprio monitor.

## Requisitos funcionais

1. Executar o observador em runner GitHub-hosted a cada 30 minutos e por acionamento manual.
2. Reutilizar o workflow canônico `Self-Hosted Runner Governance Guard`, sem criar uma nova superfície de workflow.
3. Despachar simultaneamente dois leases efêmeros pelo conjunto portátil de labels do perfil `base`, sem hostname ou `runner_id` fixo.
4. Consultar apenas os jobs da própria execução com `github.token` e permissão `actions: read`; o monitor não pode consultar o endpoint administrativo de inventário.
5. Considerar elegível somente runner distinto que conclua o preflight DEV e o lease com todas as labels requeridas pelo perfil indicado por `monitor_profile`.
6. Exigir ao menos dois runners distintos elegíveis, impedindo que um único PC satisfaça os dois slots sequencialmente.
7. Registrar achados sanitizados para lease ausente, não atribuído, incompleto, falho, desvio de labels, reutilização de runner e capacidade insuficiente.
8. Publicar artifact de evidência por 30 dias e resumo no job.
9. Operar em modo report-only: nenhuma alteração de labels, registro, processo, máquina, segredo, deploy ou ambiente é permitida.

## Restrições

- Escopo exclusivo de DEV.
- HML, STG e PROD permanecem desabilitados.
- O monitor não executa retry automático; os dois leases são jobs self-hosted controlados, somente leitura, com preflight e espera limitada.
- Cada slot usa concurrency própria com `cancel-in-progress`, para que a próxima medição substitua lease antigo ainda enfileirado.
- Um estado degradado gera aviso e evidência, sem mutação corretiva.
- Falha de autenticação ou coleta deve falhar fechado e não fabricar inventário saudável.

## Critérios de aceite

- testes unitários cobrem dois runners distintos elegíveis, lease não atribuído com drift e rejeição de dois leases atendidos pelo mesmo PC;
- o workflow usa ações externas pinadas por SHA completo;
- o observador usa `github.token` somente para os jobs da própria execução e não usa endpoint administrativo, PAT pessoal ou permissão `administration: read`;
- a evidência declara `mode=report_only`, `mutated=false`, `deploy_performed=false` e `production_touched=false`;
- o gate SDD e o orçamento de superfície de workflows ficam verdes.
