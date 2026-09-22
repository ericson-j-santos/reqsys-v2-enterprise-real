# DSC atual aplicado ao ReqSys

## Decisão

O frontend do ReqSys passa a usar o DSC atual como base visual centralizada, mantendo compatibilidade com o nome histórico do tema `figmaPadraoOuro` para não quebrar persistência local, rotas, componentes ou seleção de tema existente.

## Tokens principais

| Papel | Token | Valor | Uso recomendado |
| --- | --- | --- | --- |
| Primário institucional | `--dsc-primary` | `#005CA9` | App bar, botões primários, links, foco e navegação ativa |
| Destaque executivo | `--dsc-accent` | `#F39200` | Métricas, chamadas de atenção, pills e ações secundárias de alta relevância |
| Apoio analítico | `--dsc-teal` | `#00B3AD` | Indicadores informacionais, analytics, apoio visual e superfícies complementares |

## Arquivos alterados

- `frontend/src/theme/figmaPadraoOuro.js`
  - Centraliza `DSC_TOKENS`.
  - Preserva alias `FIGMA_TOKENS` para retrocompatibilidade.
  - Atualiza temas Vuetify escuro e claro.

- `frontend/src/styles.css`
  - Propaga variáveis CSS globais.
  - Atualiza navegação, botões, cards, métricas, pills, hover/focus e login.
  - Mantém responsividade existente.

## Fora de escopo

- Nenhuma mudança de API.
- Nenhuma mudança de banco de dados.
- Nenhuma mudança de autenticação, runtime, deploy ou workflows.
- Nenhuma troca de biblioteca visual.

## Validação esperada

Executar no CI ou localmente:

```bash
cd frontend
npm ci
npm run build
npm run test -- --runInBand || npm run test
```

Critérios de aceite:

- Build do frontend concluído.
- Tema escuro preserva contraste adequado.
- Tema claro mantém legibilidade.
- Botões primários usam azul DSC.
- Métricas e destaques executivos usam laranja DSC.
- Apoios informacionais usam turquesa DSC.
- Não há regressão de layout responsivo.
