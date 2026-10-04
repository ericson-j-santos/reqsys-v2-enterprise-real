# WCAG 2.2 AA — Critérios automatizados de teclado e foco

## Objetivo

Comprovar por execução automatizada, vinculada ao SHA corrente, os critérios WCAG 2.2 AA
que dependem de estado de interação e por isso não são detectáveis pelo `axe-core`:

| Critério do registro                 | Critérios WCAG              | Cobertura |
|--------------------------------------|-----------------------------|-----------|
| `keyboard_navigation`                | 2.1.1, 2.1.2                | automatizada |
| `focus_visibility_and_not_obscured`  | 2.4.7, 2.4.11               | automatizada |
| `zoom_and_reflow`                    | 1.4.10                      | auditoria humana |
| `text_spacing_and_content_loss`      | 1.4.12                      | auditoria humana |
| `screen_reader_critical_flows`       | 1.3.1, 4.1.2                | auditoria humana |
| `accessible_authentication`          | 3.3.8                       | auditoria humana |

O `axe-core` avalia a árvore estática e não observa foco, ordem de tabulação nem
indicador visual de foco. Esse gate cobre exatamente essa lacuna.

## Causa raiz tratada na introdução do gate

`.v-btn` do Vuetify e parte dos componentes locais redefinem `:focus-visible` com
`outline: none`. Sem uma linha de base global, 87 de 381 paradas de tabulação (22,8%)
ficavam sem nenhuma diferença visual entre o estado focado e o não focado.

A correção mínima é a regra global de foco em `frontend/src/accessibility/wcag22-aa.css`,
que reutiliza o token `--accent-strong` e não substitui os realces próprios dos componentes.

## Execução

| Etapa | Comando |
|---|---|
| Gate E2E | `npx playwright test tests/e2e/acessibilidade-teclado-foco.spec.js` |
| Contrato do validador | `npm run test:wcag22-automated-criteria` |
| Validação da evidência | `npm run validate:wcag22-automated-criteria` |
| Prontidão formal | `npm run validate:wcag22-formal` |

Encadeado em `.github/workflows/ci-e2e-governado.yml`. O roteador de E2E aciona a
execução para alterações em `frontend/src/accessibility/`, `frontend/tests/e2e/`,
`frontend/scripts/validate-wcag22-*` e `governance/accessibility/`.

## Método de medição

1. **Entrada somente por teclado** — a rota `/login` é concluída por `Tab` até o botão de
   entrada e `Enter`, sem ponteiro.
2. **Ordem de tabulação** — cada rota autenticada é percorrida por `Tab` até o ciclo
   fechar. Ciclo que não fecha dentro do limite é registrado como armadilha (SC 2.1.2).
3. **Indicador de foco** — a aparência computada do elemento, de até 16 descendentes e dos
   pseudo-elementos `::before`/`::after` é comparada entre o estado focado e o não focado.
   Aparências idênticas reprovam. A comparação cobre indicadores desenhados por `outline`,
   sombra, borda, fundo, opacidade ou camada de sobreposição.
4. **Foco não encoberto** — cinco pontos do retângulo do elemento são amostrados; o foco só
   é considerado encoberto quando todos os pontos ficam sob conteúdo posicionado como
   `fixed`/`sticky` externo ao elemento. Sobreposições internas do próprio widget não contam.
5. **Widgets compostos** — quando o contêiner ainda contém o foco após a tabulação avançar,
   a leitura sem foco é adiada e repetida até o foco deixar toda a subárvore.

## Controles contra falso positivo

- nenhuma allowlist por rota, seletor, regra ou elemento; o validador reprova o gate se
  detectar `ALLOWLIST`, `EXCECOES_ACEITAS`, `ROTAS_IGNORADAS`, `test.skip(` ou `test.fixme(`
  no código do próprio teste;
- execução sem nenhuma parada de tabulação é reprovada, e não lida como aprovação;
- critério ausente na evidência é reprovado;
- `validate-wcag22-formal-readiness.mjs` só aceita um critério `automated_gate` quando a
  evidência **da execução vigente** está presente e aprovada; arquivo ausente ou validação
  reprovada devolve o critério à condição de pendência;
- a aprovação automatizada não declara conformidade formal: `formal_status` permanece
  `pending_manual_audit` enquanto houver critério de auditoria humana em aberto.

## Registro de governança

`governance/accessibility/wcag22-aa-manual-audit.json` é a fonte canônica. Critérios com
`status: automated_gate` apontam o spec, o validador e o artifact de evidência. Os demais
permanecem `pending` e exigem auditoria humana registrada com evidência não vazia.
