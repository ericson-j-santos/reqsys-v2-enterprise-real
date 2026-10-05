# Cofre Runtime Evidence Gate — locator PC24x7 assinado

## Objetivo
Alinhar o gate do Cofre ao runtime DEV atual, eliminando a dependência obsoleta de `PC24X7_DEV_BASE_URL`.

## Requisitos
1. Resolver o runtime por `scripts/resolve_pc24x7_dev_locator.mjs`.
2. Executar o self-test Ed25519 antes da resolução remota.
3. Aceitar somente HTTPS em `*.trycloudflare.com`.
4. Não usar `PC24X7_DEV_BASE_URL`, Fly.io ou fallback estático.
5. Manter validação same-SHA e evidências sanitizadas existentes.
6. Actions externas tocadas devem usar SHA imutável.

## Critérios de aceite
- Teste de contrato do Cofre passa no HEAD exato.
- O workflow não contém `PC24X7_DEV_BASE_URL`.
- O locator assinado produz `base_url` para o job de evidência.
- Assinatura, TTL ou domínio inválidos falham fechado.
- Nenhum valor de segredo é publicado.
