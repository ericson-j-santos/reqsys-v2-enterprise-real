# Requisitos — Task Console DEV / CORS do perfil Noteri

## Problema comprovado

Na interface autenticada do GitHub Pages, o cartão **Usar o Noteri para estudo** apresenta `Network Error` e controles bloqueados. A chamada `GET /api/v1/noteri/profile` do frontend inclui `Cache-Control: no-store`. A API pública DEV aceita o preflight OPTIONS de `authorization,x-correlation-id` (HTTP 200) e rejeita o mesmo pedido com `cache-control` adicional (HTTP 400). Evidência real: GitHub Actions run `38140758588`, job `114473972831`, rota obtida exclusivamente pelo locator Ed25519 vigente.

## Correção mínima

Remover o cabeçalho `Cache-Control` **da requisição** feita pelo navegador para consultar o perfil; adicionar um parâmetro de URL único por leitura `_noteri_cache_bust` para evitar respostas antigas, sem alterar o backend, CORS allowlist, login Microsoft, permissão administrativa do POST ou estado físico do Noteri.

## Critérios de aceite

1. O navegador consulta o perfil via ReqSys, sem conexão loopback direta ao Noteri.
2. `obterPerfilNoteri()` não envia `Cache-Control` e inclui um `_noteri_cache_bust` numérico por consulta.
3. Duas leituras em sequência produzem parâmetros diferentes e preservam a validação de `host=Noteri`, `profile` e `accepts_new_development`.
4. Transições `NORMAL`/`ESTUDO` continuam exigindo administração, correlação e leitura independente após POST; nenhuma permissão é ampliada.
5. O preflight real no ambiente DEV retorna HTTP 200 para os headers permitidos, e o cenário com `cache-control` continua exercitado como controle negativo do diagnóstico inicial.
6. Testes Vitest de sucesso, cache bust, erro de backend e divergência de estado passam no HEAD da alteração; o bundle GitHub Pages compila com `VITE_BASE_PATH=/reqsys-v2-enterprise-real/dev/`.
7. A entrega ao usuário requer aprovação do Pre-PR Readiness Gate, PR/merge governados e **publicação distinta** pelo workflow autorizado de GitHub Pages.
8. O aceite E2E é a tela autenticada do usuário exibindo o perfil real do Noteri, sem `Network Error`, com controle de alternância comprovado no backend e registro do worker. Testes de código e OPTIONS, isolados, não substituem esse aceite.
9. Não alterar HML/PROD, segredos, autenticadores, permissões Microsoft ou processo do Noteri durante esse hotfix.

## Testes e evidências

- `frontend/src/services/__tests__/hostProfileLocalAgent.test.js` — regressão positiva/negativa e idempotência.
- `backend/app/api/noteri_host_profile.py` — contrato de GET autenticado e POST admin existente, sem alterações.
- Prova pré-correção: GitHub Actions `38140758588`.
- Testes frontend + build Pages da mudança: GitHub Actions `38140994935` (8 testes aprovados; código idêntico ao final).
- Validação funcional final após publicação ainda pendente.

## Regressão após publicação — divergência de correlação do POST (12/10/2026)

- Evidência de interface: Task Console autenticado apresentou `correlation_id_mismatch` e bloqueou a alternância.
- Causa determinada no código: a tela gerava `correlation_id` de operação com sufixo `-noteri-<perfil>`, mas o interceptor Axios sobrescrevia `X-Correlation-Id` com o ID geral da sessão; o POST protegido exigia igualdade e retornava HTTP 409.
- Critério positivo: POST NORMAL/ESTUDO envia exatamente o mesmo ID no corpo e no cabeçalho, sem alterar token, CORS ou verificação do backend.
- Controle negativo: backend mantém HTTP 409 quando houver divergência; frontend não marca o Noteri como pronto nem realiza leitura independente após POST rejeitado.
- Idempotência e regressão: interceptor preserva cabeçalho explícito em operações repetidas, aceita capitalização diferente, continua injetando ID de sessão quando ausente e mantém o cache-bust do GET.
- Aceite final: teste Vitest dos dois serviços, build do frontend e E2E autenticado em DEV com leitura independente do estado físico/worker. CI ou HTTP 200 isolados não comprovam o funcionamento dos botões.
