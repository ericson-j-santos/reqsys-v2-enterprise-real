# Requisitos — Monitor oficial GitHub Pages para rota DEV PC24x7

## Objetivo

Detectar somente mudanças oficiais e materialmente relevantes do GitHub Pages que possam afetar a rota DEV `GitHub Pages → locator assinado → Cloudflare → PC24x7`, sem criar custo adicional e sem alterar automaticamente a infraestrutura.

## Requisitos funcionais

1. O monitor deve reutilizar o `Scheduled Operational Watch` existente e seu agendamento de 4 horas; nenhum novo arquivo de workflow deve ser criado.
2. As fontes devem ser exclusivamente oficiais do GitHub: documentação de Pages e GitHub Changelog.
3. O escopo material deve cobrir publicação/workflows, domínio/DNS/HTTPS, limites/rate limits, segurança/takeover e compatibilidade/deprecações de Pages Actions.
4. A primeira coleta deve apenas estabelecer baseline e nunca gerar alerta histórico.
5. Falha de coleta de uma fonte deve produzir estado degradado e evidência, mas nunca ser interpretada como mudança material.
6. Mudanças documentais só podem alertar quando alterarem fatos filtrados por sinais materiais; mudanças cosméticas devem ser suprimidas.
7. O estado deve permanecer persistido na issue #2179 e a execução deve publicar artifact sanitizado.
8. Alertas devem registrar mudança confirmada, fonte oficial, risco e a menor adaptação segura, idempotente e sem custo adicional.
9. O monitor não pode alterar domínio, permissões, publicação, Cloudflare, locator, PC24x7, secrets ou produção automaticamente.
10. Após uma mudança material, a adaptação deve preservar o locator Ed25519 e exigir nova validação do fluxo real Pages → locator → Cloudflare → PC24x7 antes de conclusão.

## Critérios de aceite

- O workflow contém o job `github-pages-pc24x7-watch`.
- As cinco páginas oficiais de documentação e o feed oficial de changelog estão versionados no monitor.
- O filtro possui controles positivo e negativo executados em toda coleta.
- Baseline sem estado anterior não cria comentário.
- Erro de fonte não cria alerta por si só.
- Comentário só é criado quando `changes.length > 0`.
- A issue #2179 é a fonte persistente de estado do monitor.
- O artifact `github-pages-pc24x7-watch/report.json` é publicado com retenção de 30 dias.
- `tests/test_github_pages_watch_workflow.py` permanece verde.
- Pre-PR Readiness fica verde no HEAD exato e com `behind_by=0`.

## Risco e rollback

Mudança restrita a monitoramento/report-only em DEV. Rollback: reverter o job e os artefatos SDD/teste deste incremento. Nenhum segredo, deploy, produção ou permissão administrativa é modificado.

## Correção preventiva descoberta pelo CI

- O `npm audit` do HEAD inicial detectou `GHSA-82fw-gwwq-j7x9` em Vitest 4.1.10.
- A versão mínima de `vitest` e `@vitest/coverage-v8` deve ser 4.1.11, versão corrigida publicada pelo projeto.
- O lockfile deve resolver `vitest`, `@vitest/mocker`, `@vitest/coverage-v8` e os pacotes internos `@vitest/*` relacionados em 4.1.11.
- A correção não relaxa o gate de segurança; o `npm audit --audit-level=high` deve permanecer bloqueante.

### Critérios de aceite adicionais

- Nenhuma entrada Vitest usada pelo frontend permanece em 4.1.10.
- `npm audit --audit-level=high` não reporta `GHSA-82fw-gwwq-j7x9`.
- Build e testes do frontend permanecem verdes no mesmo HEAD.

## Correção preventiva adicional — brace-expansion

- O `npm audit` posterior detectou novos advisories de DoS em `brace-expansion` 5.0.9, incluindo `GHSA-q2hr-2g5m-vwhr`, `GHSA-qhr7-859c-m2p7` e `GHSA-6j4f-fj2g-mc7p`.
- O override deve fixar `brace-expansion` em 5.0.12, versão que cobre o conjunto de advisories observado pelo gate.
- O `npm audit --audit-level=high` continua bloqueante; não há suppress/ignore de advisory.

### Critérios de aceite adicionais — brace-expansion

- `frontend/package.json` fixa `brace-expansion` em 5.0.12.
- O lockfile resolve `node_modules/brace-expansion` em 5.0.12.
- O job `Frontend Build + Security Audit` executa `npm audit --audit-level=high` e termina verde no HEAD atual.

## Correção preventiva — governança da Issue de estado

11. O corpo persistido na Issue #2179 deve permanecer conforme o contrato de governança de Issues do ReqSys, com todas as seções obrigatórias e declaração de rastreabilidade marcada.
12. Replay sem mudança de fatos, status ou estado persistido não deve reescrever a Issue nem produzir comentário duplicado.
13. O artifact do run continua sendo a evidência temporal de cada coleta; a Issue representa o estado canônico persistente e não precisa mudar apenas para registrar horário de execução.

### Critérios de aceite adicionais — governança da Issue

- `tests/test_github_pages_watch_workflow.py` verifica as 12 seções obrigatórias e a declaração `[x]`.
- O workflow atualiza a Issue apenas quando `currentBody.trim() !== nextBody.trim()`.
- Após integração, uma coleta real transforma a #2179 em Issue governada válida.
- Uma segunda coleta sem mudança mantém o corpo da #2179 idêntico e não cria alerta material.
