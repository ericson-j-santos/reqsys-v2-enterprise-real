# ReqSys — Validação física e continuidade E2E

Site **estático, offline e em português** para registrar e organizar a execução entre `DESKTOP-PDQK954`, `DESKTOP-RP23OGS` e `Noteri`. **Não acessa hosts, não executa comandos e não atesta evidências externas.**

## Como abrir

Abra `index.html` no Chrome, Edge, Safari ou Firefox. Mantenha `index.html`, `styles.css` e `app.js` na mesma pasta. Não há servidor, Docker, pacotes ou instalação obrigatórios.

## Funções

- Visão de 10 critérios aceitos/previstos, sem contar observações como prova.
- Fila Pareto editável: issue/PR, repositório, SHA esperado e declarado, responsáveis, hosts, bloqueios e próxima ação.
- Matriz dos três hosts com identidade, labels, perfil NORMAL, sessão, Gateway, worktree, lease, runner e conectividade.
- Registro de comandos **somente texto**, resultado, logs sanitizados, antes/depois, rollback, hash SHA-256, correlação, idempotência, evidência e checkpoint de referência.
- Linha do tempo filtrável: diagnóstico sem efeito, efeito declarado, dependência humana, pickup individual, E2E e falha.
- Exportação para JSON ou relatório Markdown. Importação de JSON com confirmação explícita. Todas as alterações locais passam pela confirmação `CONFIRMAR`.
- Nenhum link externo exibido na interface; acesso remoto não verificado.

## Limites e segurança

O estado é guardado no **armazenamento deste navegador**; ele **não é a fonte canônica TODO Global nem checkpoint durável entre máquinas**. Exportar é recomendado; importação substitui a cópia local. Em modo privado ou políticas restritas, o navegador pode bloquear o armazenamento. Não registrar dados pessoais (LGPD), chaves, senhas, tokens, contratos nem logs confidenciais. Há mascaramento básico de tokens, mas **isso não substitui a revisão humana do conteúdo**.

O painel foi configurado para **não aceitar nenhum critério como fisicamente comprovado** sem uma integração futura com testemunho autenticado e independente no ambiente real. Assim, o percentual comprovado permanece 0% (corretamente) enquanto essa capacidade não existir. O preenchimento de requisitos mostra apenas documentação declarada. Um host só pode ser homologado no fluxo operacional real após preflight autenticado, prova física de identidade e operação, SHA exato, lease exclusiva, readback independente e teste E2E positivo/negativo com replay.

Todos os comandos são texto. Não há `fetch`, chamadas a API, dispatch, reboot, merge, push, alteração administrativa, automação por GUI ou Docker. Publicação e sincronização não estão implementadas. Qualquer adaptação para mutações remotas exigirá autorização específica por ação, host, ambiente, custo, SHA e rollback.

## Governança lida em 13/11/2026

- Fonte canônica: `ericson-j-santos/chatgpt-operational-rules` branch `main` SHA `58dcd4200f412a866278027ba9e433439a03f3b3`, versão `1.6.21`.
- Foram consultados README, AGENTS, projetos ReqSys, Runtime Platform e Engineering Control Plane, além de governança de custo, E2E, terminal/Gateway, preflight, armazenamento e TODO Global.
- ReqSys `main` consultada em 13/11/2026: `a05e64bbc58a15314b42cfa9314f1d415535b05b` (somente repositório GitHub, não prova física do host).
- ReqSys Produto segue prioridade P0; Runtime Platform cuida dos hosts físicos; Control Plane dos gates transversais.
- Custo incremental máximo: **R$ 0,00**. Não há dependências externas de execução do site.

## Testes

`node --check app.js`, `node tests/smoke_node.cjs`, `python -m pytest -q tests/test_static.py` e `python -m pytest -q tests/test_browser_offline.py`. **Resultados de 13/11/2026:** 12 verificações lógicas JS, 7 testes estáticos e 6 testes de interação no Chromium sem rede aprovados. A suíte `tests/test_site.py` tenta abrir o site por HTTP em `127.0.0.1`, mas essa navegação foi bloqueada pela política do ambiente; os testes offline não substituem E2E HTTP em servidor, nem E2E físico nos hosts. Não contornar a política.

## Próximo passo para comprovação real

Conectar um serviço **autenticado e somente leitura** que consulte o plano de controle e devolva atestações independentes com `host`, `runner`, `SESSION_LAUNCH_OK`, `state_validated`, lease/worktree exclusivos, `correlation_id`, `idempotency_key`, SHA, checkpoint durável, efeitos e readback. A aceitação deve ser feita no sistema canônico, não no navegador. Depois, validar fisicamente dois hosts reais e recuperação sem duplicação. **Sem correção, deploy ou execução física aplicada por este artefato.**
