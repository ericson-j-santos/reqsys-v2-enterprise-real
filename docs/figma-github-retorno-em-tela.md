# Figma GitHub — retorno em tela

## Objetivo

Implementar no ReqSys uma tela operacional para executar sincronização Figma/GitHub e exibir o retorno em tela, com rastreabilidade, governança e evidência visual.

## URL funcional

- `/figma-github`

## Backend utilizado

A tela consome os endpoints já existentes:

- `POST /v1/integracoes/figma-github/sync`
- `GET /v1/integracoes/figma-github/status`

## Capacidades implementadas

- Formulário de sincronização governada.
- Suporte aos modos:
  - `bidirectional`;
  - `figma_to_github`;
  - `github_to_figma`.
- Parâmetros opcionais:
  - `file_key`;
  - `repo`;
  - `node_ids`;
  - comentários;
  - frames;
  - dev resources.
- Retorno da última sincronização em tela.
- Tabela analítica dos vínculos Figma/GitHub.
- Filtro por status.
- Links para issues GitHub quando retornados pelo backend.
- Estados de loading, sucesso e erro.
- Layout responsivo com tabela horizontal em telas menores.

## Governança

- Nenhum segredo é exposto no frontend.
- A tela apenas consome endpoints governados pelo backend.
- A publicação depende de CI verde, revisão e validação E2E.
- A rota exige o mesmo recurso de leitura de dashboard usado em painéis operacionais.

## Pendências conhecidas

- Validar build frontend e fluxo E2E após execução do CI.
- Configurar `FIGMA_ACCESS_TOKEN`, `FIGMA_DEFAULT_FILE_KEY` e `FIGMA_GITHUB_DEFAULT_REPO` nos ambientes que forem usar sync real.

## Checklist de produção

| Item | Estado |
|---|---|
| View frontend | Implementado |
| Rota `/figma-github` | Implementado |
| Retorno em tela | Implementado |
| Analítico em tabela | Implementado |
| Filtro por status | Implementado |
| Menu lateral | Implementado |
| Frente/tópico no Mapa da Solução | Implementado |
| Registro em Living Architecture Index | Implementado |
| Tópico Copilot Studio (Sincronizar Figma GitHub) | Documentado |
| Teste local | Pendente |
| CI | Pendente |
| Deploy produção | Bloqueado até CI verde |
