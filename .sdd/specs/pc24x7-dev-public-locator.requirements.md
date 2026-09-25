# Requisitos — Locator público DEV zero-cost

## Objetivo

Fornecer uma URL estável para o ambiente DEV sem domínio pago, token DuckDNS,
consentimento Tailscale ou dependência de um subdomínio NPort que possa ficar
preso após crash.

## Arquitetura

```text
GitHub Pages /dev/
      |
      +--> lê estado assinado do ntfy
                  |
PC24x7 --Ed25519--> ntfy.sh
  |
  +--> Cloudflare Quick Tunnel A --> :8083
  +--> Cloudflare Quick Tunnel B --> :8083
```

## Requisitos

1. A URL estável deve ser
   `https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/`.
2. A chave privada Ed25519 deve permanecer somente no PC24x7 e protegida por
   Windows DPAPI.
3. O repositório pode conter somente a chave pública e o tópico público.
4. O publisher deve aceitar como destino somente URLs HTTPS
   `*.trycloudflare.com` que respondam `/api/health` com HTTP 200.
5. Cada payload deve expirar em no máximo 15 minutos.
6. O locator deve ignorar mensagens inválidas, não assinadas, expiradas ou de
   ambiente diferente de DEV.
7. A tarefa local deve publicar novo estado a cada ciclo de 5 minutos.
8. Cloudflare Quick Tunnel permanece o transporte; GitHub Pages é apenas a
   entrada estável/descoberta.
9. Tailscale, DuckDNS e NPort não podem bloquear o DEV.
10. HML e PROD permanecem fora deste incremento.
11. Merge, push, schedule e conclusão de outro workflow não podem publicar GitHub Pages automaticamente; o deploy deve aceitar somente `workflow_dispatch` explícito a partir de `main`.
12. O deploy deve exigir `authorization=DEPLOY_PAGES` e `expected_sha` completo igual ao HEAD atual de `main`; divergência deve falhar antes do checkout/publicação. O run produtor do dashboard Teams deve ser resolvido separadamente e validado como bem-sucedido.
13. A `Validação de Acessos Públicos — ReqSys` deve executar após qualquer Pull Request realmente mergeada em `main`, usando `pull_request: closed`, exigindo `merged=true` e validando o `merge_commit_sha` exato. O gatilho `workflow_run` não deve ser usado para essa prova pós-merge.
14. Consumidores CI do runtime DEV não podem depender de uma URL Quick Tunnel estática; devem resolver o locator público assinado vigente.
15. A resolução em CI deve validar Ed25519, ambiente DEV, TTL máximo de 15 minutos, `issued_at`, `selected_url` pertencente à lista e somente HTTPS `*.trycloudflare.com`; qualquer divergência falha fechada.
16. O publisher local só pode publicar URLs que respondam HTTP 200 em `/api/health`, `/api/runtime/health` e `/api/runtime/build-info`.
17. O supervisor não pode publicar locator quando o contrato runtime local estiver parcial; nesse caso deve registrar `local_runtime_contract_failed`, manter `ready=false` e deixar o locator anterior expirar naturalmente.
18. Toda validação de publicação same-SHA deve comparar o SHA observado exclusivamente com o `expected_sha` imutável da execução; coincidir apenas com o HEAD atual de `main` não é evidência válida e deve falhar fechado.
19. O cutover DEV não é concluído apenas pela existência do PC24x7: caminhos críticos de navegação, configuração e smoke não podem depender, redirecionar ou usar fallback silencioso para `reqsys-app-dev.fly.dev` ou `reqsys-api-dev.fly.dev`.
20. Smokes públicos de DEV devem resolver o mesmo locator Ed25519 vigente; um resultado funcional diferente de `passed` deve produzir workflow vermelho, mesmo quando o artefato de análise continuar `report-only` para decisão executiva.
21. A navegação para DEV deve usar a entrada estável GitHub Pages e encaminhar somente uma rota relativa validada ao Quick Tunnel selecionado; URL absoluta ou `//host` não pode ser aceita como destino.
22. Alterações do Modo ESTUDO integradas em `main` devem disparar reconciliação DEV no runner `pc24x7` e validar NORMAL→ESTUDO→replay idempotente→NORMAL sem tocar HML/PROD.
23. Smokes executivos acionados por `deployment_status` devem exigir `environment_url` pública não vazia antes de resolver o locator DEV; eventos genéricos do GitHub Environment sem URL pública devem ser ignorados, enquanto `workflow_dispatch` explícito permanece disponível. Esse filtro não pode converter falha funcional de um alvo público real em sucesso.
24. O payload assinado deve declarar `runtime_contract.version=2.0.0`, os quatro endpoints obrigatórios (`/api/health`, `/api/runtime/health`, `/api/runtime/readiness`, `/api/runtime/build-info`), `static_frontend_required=true` e `vite_hmr_forbidden=true`. Pages e o resolver CI devem rejeitar locators antigos que não carreguem esse contrato assinado, mesmo quando assinatura, TTL e host forem válidos.

## Critérios de aceite

- testes do contrato passam;
- publisher local retorna HTTP 200 no ntfy;
- mensagem é legível externamente;
- GitHub Pages publica `/dev/`;
- `/dev/` valida assinatura e redireciona apenas para tunnel vigente;
- task scheduler preserva bateria/StartWhenAvailable/timeout de 10 minutos;
- merge, push, schedule e `workflow_run` não disparam publicação de Pages;
- `workflow_dispatch` com autorização ausente/incorreta ou SHA divergente falha fechado antes da publicação;
- `workflow_dispatch` autorizado opera somente sobre o SHA exato da `main` informado em `expected_sha`;
- validação pública pós-merge é disparada automaticamente por `pull_request: closed` somente quando `merged=true`, valida o `merge_commit_sha` exato e falha se o alvo obrigatório estiver indisponível;
- nenhuma dependência paga é introduzida;
- o workflow de promoção automática resolve o tunnel vigente pelo locator assinado e não usa `vars.PC24X7_DEV_BASE_URL`/`vars.PC24X7_DEV_FRONTEND_URL` como URL efêmera estática;
- runtime parcial (health básico verde, mas runtime health/build-info ausentes) nunca é republicado pelo locator.
- teste negativo comprova que runtime no SHA atual de `main`, porém diferente do `expected_sha`, é rejeitado como `sha_mismatch`.
- gate preventivo bloqueia referências Fly.io DEV nos caminhos críticos do cutover;
- navegação DEV usa `/dev/?target=<rota-relativa>` e o locator rejeita alvo absoluto/protocol-relative;
- smoke DEV com falha funcional não pode terminar verde;
- `deployment_status` sem `environment_url` pública não dispara smoke executivo; com URL pública, o smoke continua fail-closed;
- merge em `main` de arquivos do Modo ESTUDO dispara reconciliação física no PC24x7.
