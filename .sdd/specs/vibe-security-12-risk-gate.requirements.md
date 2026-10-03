# Vibe Coding — 12-risk Security Gate — Requisitos

## Objetivo

Consolidar os 12 riscos do guia KipperDev em um gate versionado e verificável do ReqSys, reutilizando a esteira de segurança atual sem criar fan-out desnecessário de workflows.

## Classificação

`consolidate`. Mudança reversível de CI e documentação, sem deploy, promoção de ambiente, alteração de segredo ou produção.

## Requisitos funcionais

1. O gate deve manter exatamente 12 categorias, correspondentes a: segredos no frontend, validação de entradas, SQL injection, prompt injection, XSS, IDOR/BOLA, SSRF, senhas, abuso de requisições, rotas administrativas, bots e vazamento em mensagens de erro.
2. Achados estáticos de alta confiança podem usar `enforcement=block`; riscos dependentes de autorização, infraestrutura ou comportamento de runtime devem usar `review_required` em vez de afirmar segurança.
3. Ausência de padrão deve resultar em `no_signal`, nunca em `safe`, `secure` ou equivalente.
4. O relatório deve registrar arquivo, linha, evidência sanitizada, severidade, enforcement e ação de correção/validação.
5. O scanner deve operar offline/read-only, sem ler secrets, sem fazer chamadas externas e sem alterar runtime.
6. O scanner deve aceitar escopo `all` e `changed`, compatível com o escopo já resolvido pelo `Security Baseline Gate`.
7. O modo `--strict` deve falhar somente quando houver ao menos um achado `block`.
8. O próprio scanner deve conter controle negativo capaz de provar que uma exposição pública de segredo no frontend é detectada.
9. O workflow existente `.github/workflows/security-baseline-gate.yml` deve executar o novo gate; não criar novo workflow para esta consolidação.
10. Os relatórios JSON e Markdown devem ser publicados dentro do artifact já existente `security-baseline-report`.
11. Gitleaks, CodeQL, Bandit, pip-audit, npm audit e SBOM existentes permanecem complementares e não devem ser removidos ou enfraquecidos.
12. A documentação deve definir evidência positiva/negativa e explicitar que busca textual não comprova segurança.
13. Arquivos de teste do frontend em `__tests__`, `*.test.*` e `*.spec.*` não devem compor o escopo de código de produção do scanner, evitando falso bloqueio por fixtures deliberadamente inseguras.
14. Sinks `v-html` de produção continuam bloqueadores quando não houver sanitização explícita; o renderer de Markdown do Specs deve sanitizar a saída com DOMPurify antes de entregá-la ao DOM.
15. A sanitização deve possuir teste negativo para `<script>`, event handlers e protocolo `javascript:`, além de controle positivo que preserve Markdown seguro.
16. Quando a sanitização estiver encapsulada em helper importado, o scanner só pode rebaixar o sink para revisão se validar o consumidor exato, o caminho exato do helper e a presença real da chamada de sanitização nesse helper; remover a sanitização do helper deve restaurar `enforcement=block`.
17. Em `pull_request`, `merge_group` e `push` para `main`, o enforcement estrito deve avaliar apenas a dívida introduzida pelo delta corrente; em `push`, o intervalo deve usar `github.event.before...github.sha` para cobrir o conjunto real de commits publicado.
18. Todo `push` em `main` deve gerar também um snapshot `scope=all` report-only, preservando visibilidade integral da dívida histórica sem convertê-la em falso bloqueio da nova versão.
19. `workflow_dispatch` deve continuar permitindo `scope=all` + modo estrito para auditoria deliberada do repositório completo.

## Critérios de aceite

- `tests/test_vibe_security_gate.py` comprova a matriz 01–12 sem duplicidade.
- Um conjunto controlado de falhas de alta confiança é detectado como bloqueador.
- Sinais contextuais são marcados para revisão e não geram falso "seguro".
- Exemplos parametrizados/sanitizados não geram bloqueador indevido no teste de controle.
- Fixtures de teste do frontend ficam fora do scan de produção, mas um `v-html` equivalente em arquivo de produção continua bloqueando.
- O renderer de Markdown remove script, event handlers e URLs `javascript:` e preserva conteúdo seguro em teste automatizado.
- O gate comprova a cadeia `SpecsView.vue` → `markdownRenderer.js`; regressão que remova `DOMPurify.sanitize` do helper volta a bloquear.
- Relatório sem achados contém as 12 linhas com `no_signal` e a ressalva de garantia.
- O controle negativo interno retorna sucesso somente quando a falha conhecida é detectada.
- O workflow compila e executa o novo gate em modo estrito no mesmo escopo incremental do evento.
- `push` em `main` falha por blocker novo no delta, não por blocker histórico fora do delta; o snapshot completo continua publicado como report-only.
- O SDD Gate e o Pre-PR Readiness devem ficar verdes no HEAD exato e com `behind_by=0`.
- Nenhum merge, deploy, produção ou mudança de segredo faz parte deste incremento.
