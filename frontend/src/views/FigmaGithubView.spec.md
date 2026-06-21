# Cenários de teste — Figma GitHub View

> Especificação viva para orientar testes unitários, integração e E2E da tela `/figma-github`.

## Cenários mínimos

| ID | Tipo | Dado | Quando | Então |
|---|---|---|---|---|
| FG-001 | Renderização | Usuário autenticado com permissão `dashboard:read` | Acessa `/figma-github` | A tela exibe título, formulário, cards e tabela |
| FG-002 | Status | Backend retorna `items` | A tela carrega | A tabela lista vínculos Figma/GitHub |
| FG-003 | Filtro | Existem múltiplos status | Usuário seleciona um status | A tabela exibe apenas itens filtrados |
| FG-004 | Sync | Usuário informa payload válido | Envia sincronização | A tela exibe retorno da API e recarrega status |
| FG-005 | Erro sync | Backend retorna erro | Envia sincronização | A tela exibe mensagem de erro sem quebrar layout |
| FG-006 | Responsivo | Viewport mobile | Acessa a tela | Cards refluem e tabela mantém rolagem horizontal |
| FG-007 | Segurança | API retorna dados sem segredos | Renderiza resultado | Nenhum token/segredo é exibido |

## Comandos recomendados após checkout local

```bash
cd frontend
npm ci
npm run build
npm run test -- --run
```

## Gate

A feature só pode avançar para produção após:

- build frontend verde;
- testes automatizados verdes;
- validação manual/E2E da rota `/figma-github`;
- atualização do menu lateral quando o bloqueio do conector for resolvido;
- CI completo verde no PR.
