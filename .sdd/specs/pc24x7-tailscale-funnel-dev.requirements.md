# Requisitos — PC24x7 Tailscale Funnel DEV

## Objetivo

Disponibilizar URL HTTPS estável para o ReqSys DEV no PC24x7 sem Fly.io, sem domínio próprio,
sem abertura de portas do roteador e sem publicar o backend diretamente.

## Requisitos funcionais

1. O nó Tailscale deve estar autenticado e com MagicDNS ativo.
2. O Funnel deve encaminhar exclusivamente para o gateway ReqSys DEV em `:8083`.
3. A URL pública deve ser derivada do `Self.DNSName` do Tailscale e terminar em `.ts.net`.
4. A validação deve comprovar HTTP 200 em `/api/health` e `/task-console`.
5. Nenhum segredo deve ser armazenado pelo reconciliador.
6. HML e PROD não podem ser alterados por este incremento.

## Critérios de aceite

1. Testes validam derivação do hostname estável e alvo DEV `:8083`.
2. Tailscale reporta `BackendState=Running`.
3. MagicDNS está habilitado.
4. Funnel fica ativo em background para o gateway DEV.
5. Leitura pública independente retorna HTTP 200 em `/api/health`.
6. Leitura pública independente retorna HTTP 200 em `/task-console`.
7. Nenhuma promoção de HML/PROD ocorre.
