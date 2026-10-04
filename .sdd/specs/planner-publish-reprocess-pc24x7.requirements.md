# Reprocessamento Planner Publish no PC24x7 DEV — Requisitos

## Objetivo

Corrigir o reprocessamento automático de publicações do Planner para usar o
runtime PC24x7 DEV e uma rota de leitura compatível com autenticação S2S, sem
recorrer ao runtime Fly.io legado nem ocultar configuração ausente.

## Requisitos

1. O workflow deve obter a base da API exclusivamente de `REQSYS_API_BASE_URL`
   no GitHub Environment selecionado.
2. A base da API deve usar HTTPS e não pode conter credenciais, query, fragmento
   ou hostname `fly.dev`/subdomínio de `fly.dev`.
3. URL ausente ou inválida deve encerrar a execução antes de expor ou enviar o
   token de serviço.
4. `PLANNER_PUBLISH_SERVICE_TOKEN` ausente deve bloquear o reprocessamento, sem
   produzir falso sucesso.
5. A API deve expor uma listagem S2S limitada às tentativas no estado
   `falhou_integracao`, autorizada para administrador ou token com o escopo
   `planner_publish:enviar`.
6. O script deve consumir a rota S2S de pendências e preservar no backend as
   decisões de idempotência, limite de tentativas e recusa de duplicidade.
7. Respostas HTTP inesperadas devem falhar no modo `--strict`; recusas esperadas
   do backend por HTTP 409 devem permanecer registradas como desfecho governado.
8. O token de serviço não pode ser impresso nem persistido na evidência.
9. O backend, o script e o workflow devem ser publicados juntos antes da primeira
   execução no DEV configurado.
10. Este incremento não autoriza deploy, promoção de ambiente, criação de segredo
    nem envio de mensagem externa.

## Critérios de aceite

- o endpoint de pendências aceita um token com `planner_publish:enviar` e rejeita
  token com outro escopo ou requisição sem credencial;
- a consulta repassa ao serviço o filtro `falhou_integracao` e o limite validado;
- o workflow rejeita URL vazia, HTTP, Fly.io, credenciais e query antes de gravar
  qualquer output;
- uma URL HTTPS PC24x7 válida preserva o prefixo de caminho configurado;
- as GitHub Actions externas do workflow usam SHAs completos e imutáveis;
- os testes direcionados e o contrato SDD passam no HEAD final da PR.

## Fora do escopo

- provisionar URL ou token no GitHub Environment;
- executar reprocessamento real antes de publicar backend e script no mesmo SHA;
- alterar a recorrência de 30 minutos;
- homologar Planner, Teams ou Redmine em HML/PROD.
