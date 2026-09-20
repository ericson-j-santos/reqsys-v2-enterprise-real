# Requisitos — PC24x7 Public DEV Ingress

## Objetivo

Publicar o ambiente DEV do ReqSys pelo PC24x7 sem dependência operacional de Fly.io e sem
acoplar os túneis ao endereço IPv4 LAN do host.

## Requisitos funcionais

1. O gateway público DEV deve terminar no Nginx do ambiente em `:8083`.
2. Os containers `reqsys-dev-gateway-tunnel` e `reqsys-dev-failover-tunnel` devem usar
   `http://host.docker.internal:8083`.
3. A reconciliação deve ser idempotente e só recriar container quando houver drift.
4. Cada túnel deve usar `restart: unless-stopped`.
5. A validação deve comprovar HTTP 200 em `/api/health` e `/task-console`.
6. URLs Quick Tunnel devem ser tratadas como estado runtime, nunca hardcoded no Git.
7. Nenhuma porta de backend deve ser adotada como entrada pública canônica.
8. DuckDNS permanece alvo de URL estável, mas não pode ser promovido sem credencial protegida
   e ingresso HTTPS comprovado.
9. HML e PROD não são promovidos por este incremento.

## Requisitos não funcionais

- Nenhum segredo em Git, chat, logs ou artifacts.
- A troca do IPv4 LAN do host não pode exigir reconfiguração do túnel.
- Falha de health/readiness deve resultar em estado não pronto.
- O estado runtime local deve ser persistido fora do repositório.

## Critérios de aceite

1. Testes automatizados comprovam extração de URLs, idempotência de configuração e rejeição
   do alvo LAN antigo.
2. O reconciliador aceita como canônico `host.docker.internal:8083`.
3. Os dois túneis reais ficam `running`, com `restart=unless-stopped`.
4. `/api/health` retorna HTTP 200 em ambos os túneis.
5. `/task-console` retorna HTTP 200 em ambos os túneis.
6. O manifesto público não contém `fly.dev` nem target Fly obrigatório.
7. Nenhuma promoção de HML/PROD ocorre neste incremento.
