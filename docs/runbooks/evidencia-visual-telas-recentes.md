# Evidência visual — telas das últimas implementações

Data de referência: 2026-06-29

## Objetivo

Quando o usuário pedir para **ver as telas**, **mostrar implementações recentes** ou **evidência visual** do produto, o agente deve entregar **sempre** os três artefatos abaixo, sem esperar nova confirmação:

1. **Screenshots em tela cheia** das rotas mais recentes.
2. **Walkthrough em vídeo** navegando entre as telas.
3. **Aprofundamento técnico** (o que mudou, rotas, contratos, limitações do ambiente).

## Gatilhos (sempre aplicar)

- "Traga as telas…"
- "Mostre as últimas atualizações/implementações"
- "Evidência visual"
- "Walkthrough das telas"
- Retorno pós-merge ou pós-incremento quando o escopo incluir frontend

## Pré-condições

- Backend (`:8000`) e frontend (`:5173`) rodando em modo dev (ver `AGENTS.md`).
- Login demo: e-mail `ericsonjosedossantos@tieri659.onmicrosoft.com` (senha ignorada).
- Exportar `GATEWAY_PORT=5173` ao subir o Vite direto.

## Rotas canônicas (atualizar após cada entrega relevante)

| Prioridade | Rota | PR / entrega | Destaque |
| --- | --- | --- | --- |
| 1 | `/govbi-ia` | #534 | Painel de funcionamento 100% (14/14 testes local + API) |
| 2 | `/segredos-status` | #531 | Diagnóstico de cofre/segredos sem expor valores |
| 3 | `/figma-github` | #529 | Sync governado Figma ↔ GitHub |
| 4 | `/monitoramento-operacional` | #461 / #532 | Runtime navegável + governance cards |
| 5 | `/governanca` | Tier 1 | Baseline 100%, 11 gates, ciclo operacional |
| 6 | `/` | #497 | Dashboard Trilha C com semáforo e drill-down |

## Passos executáveis

```text
1. git log --oneline -10 -- frontend/src/views/   # confirmar telas recentes
2. Subir backend + frontend (tmux ou terminal dedicado)
3. Login demo em /login
4. Para cada rota da tabela:
   - Navegar em viewport maximizado
   - Aguardar carregamento
   - Capturar screenshot full-screen em /opt/cursor/artifacts/screenshots/
5. Gravar vídeo (RecordScreen) percorrendo as mesmas rotas
   - Em /govbi-ia: clicar "Testes" e pausar no painel 100%
6. No retorno ao usuário:
   - Embutir screenshots e vídeo
   - Tabela resumo PR × rota × destaque
   - Aprofundamento técnico por tela (arquivos, APIs, gotchas)
7. Ao encerrar sessão dev:
   - NÃO commitar backend/reqsys.db
   - Parar uvicorn antes de git restore backend/reqsys.db
```

## Artefatos esperados

| Artefato | Caminho sugerido |
| --- | --- |
| Screenshots | `/opt/cursor/artifacts/screenshots/<nome-descritivo>.webp` |
| Vídeo walkthrough | `/opt/cursor/artifacts/walkthrough-ultimas-implementacoes-reqsys.mp4` |

## Limitações conhecidas (ambiente dev local)

- **Figma GitHub**: status pode falhar sem `GITHUB_TOKEN` / `FIGMA_*` configurados.
- **Monitoramento**: runtime dashboard pode exibir "carregando" sem artefatos de governança publicados.
- **GovBI**: proxy funciona; modo degradado é esperado se serviço externo estiver indisponível.

## Banco de informações (memória operacional)

Este runbook é a fonte canônica para o padrão **desenvolver → absorver → aplicar**:

- **Desenvolver**: implementar/capturar evidência visual após entregas de frontend.
- **Absorver**: registrar rotas e PRs na tabela acima e em `ENGINEERING_PLAYBOOKS.md` §9.
- **Aplicar**: todo agente Cloud/local segue este fluxo ao responder pedidos de telas.

## Referências

- [`AGENTS.md`](../../AGENTS.md) — serviços canônicos e gotchas
- [`docs/padrao-ouro/ENGINEERING_PLAYBOOKS.md`](../padrao-ouro/ENGINEERING_PLAYBOOKS.md) — playbook §9
- [`docs/runbooks/trilha-c-ux-operacional.md`](trilha-c-ux-operacional.md) — Trilha C UX
