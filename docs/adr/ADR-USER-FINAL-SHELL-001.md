# ADR-USER-FINAL-SHELL-001 — Shell de Produto e Navegação do Usuário Final

## Status

Proposto para PR-001A.

## Contexto

O ReqSys já possui fundações de governança, CI/CD, runtime e documentação viva, mas ainda precisa consolidar uma camada de produto final acessível para usuário final. A liberação controlada exige uma experiência mínima navegável, responsiva, clara e rastreável.

O objetivo deste ADR é definir o contrato de shell de produto antes da implementação visual, reduzindo risco de conflito com PRs ativos e evitando acoplamento prematuro a uma estrutura frontend ainda em estabilização.

## Decisão

Criar um shell de produto para usuário final com navegação principal explícita, estados visuais padronizados e indicação clara de ambiente.

O shell deve ser tratado como camada transversal de experiência, não como página isolada.

## Escopo do shell

O shell deve conter:

- cabeçalho com identificação do produto;
- indicador de ambiente: `DEV`, `HML` ou `PRD`;
- menu principal;
- área de conteúdo;
- cards operacionais;
- estados padrão de carregamento, vazio, erro e sucesso;
- rodapé técnico mínimo com versão, ambiente e `correlation_id` quando disponível.

## Navegação mínima

| Rota lógica | Objetivo | Maturidade inicial |
|---|---|---|
| `/` ou `/home` | Entrada operacional do usuário final | Obrigatória |
| `/workspace` | Área principal de trabalho | Obrigatória |
| `/requisitos` | Catálogo de requisitos | Obrigatória |
| `/analytics` | Indicadores e drill-down | Inicial |
| `/govbi-ia` | BI conversacional governado | Existente/em evolução |
| `/governanca` | Evidências, gates e auditoria | Inicial |
| `/ajuda` | Onboarding e orientação rápida | Obrigatória |

## Estados visuais obrigatórios

Todo componente navegável deve prever:

| Estado | Uso | Comportamento esperado |
|---|---|---|
| `loading` | Dados em carregamento | Exibir feedback não bloqueante |
| `empty` | Sem dados | Explicar o próximo passo |
| `error` | Falha operacional | Exibir mensagem clara e caminho de recuperação |
| `success` | Dados disponíveis | Exibir conteúdo e ações primárias |
| `unauthorized` | Acesso negado | Orientar login/permissão |

## Responsividade

O shell deve ser mobile-first e manter:

- menu colapsável em telas pequenas;
- cards em uma coluna no mobile;
- tabelas com fallback para cards ou rolagem controlada;
- ações principais sempre visíveis;
- contraste suficiente para leitura executiva.

## Ambientes

O shell deve exibir o ambiente atual com semântica visual:

| Ambiente | Exibição | Regra |
|---|---|---|
| DEV | Desenvolvimento | Pode exibir dados simulados |
| HML | Homologação | Deve sinalizar validação |
| PRD | Produção | Não pode operar com configuração insegura |

Em produção, deve haver bloqueio operacional quando:

- autenticação estiver desligada;
- CORS estiver aberto com `*`;
- JWT não validar issuer/audience;
- logs expuserem token, senha, CPF, PII ou connection string;
- auditoria crítica não tiver `correlation_id`.

## Drill-down

Cards e indicadores devem ser clicáveis quando houver detalhamento disponível.

Contrato mínimo de drill-down:

```json
{
  "source": "dashboard-card",
  "metric": "requisitos_pendentes",
  "filters": {
    "status": "pendente"
  },
  "correlation_id": "opcional"
}
```

## Acessibilidade e UX

O shell deve priorizar:

- linguagem clara para usuário final;
- nomes de menu orientados a negócio;
- foco visual em próxima ação;
- contraste e espaçamento adequados;
- feedback de erro compreensível;
- ausência de dependência exclusiva de cor para status.

## Observabilidade mínima

Eventos de navegação e falhas relevantes devem poder gerar:

- `correlation_id`;
- timestamp UTC;
- rota lógica;
- ambiente;
- status operacional;
- mensagem segura sem PII.

## Critérios de aceite do PR-001B

A implementação visual será aceita quando:

- existir tela inicial navegável;
- houver menu principal;
- rotas mínimas não quebrarem;
- estados `loading`, `empty`, `error` e `success` estiverem representados;
- ambiente atual estiver visível;
- layout responder em desktop e mobile;
- não houver vazamento de segredo/PII;
- CI permanecer verde.

## Consequências

### Positivas

- reduz ambiguidade de implementação;
- cria padrão reutilizável para novas abas;
- melhora experiência de usuário final;
- prepara analytics/drill-down;
- preserva governança de ambientes.

### Riscos

- implementação visual pode variar conforme stack/frontend real;
- PRs abertos podem conflitar se alterarem rotas/layouts;
- contrato precisa ser mantido vivo conforme produto evoluir.

## Próximo incremento

Implementar o **PR-001B — Shell visual e navegação mínima**, respeitando este ADR e mantendo escopo pequeno.
