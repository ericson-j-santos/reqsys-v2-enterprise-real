# Requisitos — monitor do pool de runners ReqSys DEV

## Objetivo

Detectar periodicamente indisponibilidade e desvio de labels no pool portátil de runners ReqSys DEV, sem depender de um host específico para executar o próprio monitor.

## Requisitos funcionais

1. Executar em runner GitHub-hosted a cada 30 minutos e por acionamento manual.
2. Reutilizar o workflow canônico `Self-Hosted Runner Governance Guard`, sem criar uma nova superfície de workflow.
3. Consultar o inventário de runners com a credencial governada `GH_PAT_ACTIONS` e acesso somente de leitura durante o monitoramento.
4. Considerar elegível somente runner online com todas as labels definidas em `config/reqsys-dev-runner-pool.json`.
5. Exigir ao menos dois runners elegíveis online.
6. Registrar achados sanitizados para runner offline, desvio de labels e capacidade online insuficiente.
7. Publicar artifact de evidência por 30 dias e resumo no job.
8. Operar em modo report-only: nenhuma alteração de labels, registro, processo, máquina, segredo, deploy ou ambiente é permitida.

## Restrições

- Escopo exclusivo de DEV.
- HML, STG e PROD permanecem desabilitados.
- O monitor não executa retry automático nem despacha jobs self-hosted.
- Um estado degradado gera aviso e evidência, sem mutação corretiva.
- Falha de autenticação ou coleta deve falhar fechado e não fabricar inventário saudável.

## Critérios de aceite

- testes unitários cobrem dois runners elegíveis e o cenário offline com drift de labels;
- o workflow usa ações externas pinadas por SHA completo;
- o workflow usa `GH_PAT_ACTIONS`, não `github.token`, para o endpoint administrativo de inventário;
- a evidência declara `mode=report_only`, `mutated=false`, `deploy_performed=false` e `production_touched=false`;
- o gate SDD e o orçamento de superfície de workflows ficam verdes.
