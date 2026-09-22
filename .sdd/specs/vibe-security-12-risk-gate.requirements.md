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

## Critérios de aceite

- `tests/test_vibe_security_gate.py` comprova a matriz 01–12 sem duplicidade.
- Um conjunto controlado de falhas de alta confiança é detectado como bloqueador.
- Sinais contextuais são marcados para revisão e não geram falso "seguro".
- Exemplos parametrizados/sanitizados não geram bloqueador indevido no teste de controle.
- Relatório sem achados contém as 12 linhas com `no_signal` e a ressalva de garantia.
- O controle negativo interno retorna sucesso somente quando a falha conhecida é detectada.
- O workflow compila e executa o novo gate em modo estrito no mesmo escopo do baseline.
- O SDD Gate e o Pre-PR Readiness devem ficar verdes no HEAD exato e com `behind_by=0`.
- Nenhum merge, deploy, produção ou mudança de segredo faz parte deste incremento.
