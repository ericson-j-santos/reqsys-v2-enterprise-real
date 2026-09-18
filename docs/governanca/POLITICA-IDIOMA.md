# Política de idioma — Português primeiro

## Estado

- Versão: 1.0.0
- Vigência: imediata para artefatos novos ou modificados
- Responsável: governança técnica do ReqSys
- Modo inicial: consultivo, sem bloqueio da integração contínua

## Decisão

Todo conceito pertencente ao domínio do ReqSys deve ser nomeado em português. O inglês é permitido somente quando imposto por protocolo, biblioteca, ferramenta, produto externo ou contrato legado cuja alteração cause incompatibilidade.

## Abrangência

A política aplica-se a requisitos, documentação, código próprio, banco de dados, contratos de API novos, registros, mensagens, testes, painéis, alertas, solicitações de alteração e mensagens de confirmação.

## Regras

1. Usar o glossário canônico antes de criar um novo termo de domínio.
2. Preferir nomes claros em português a traduções literais pouco naturais.
3. Preservar palavras reservadas, cabeçalhos, formatos e identificadores definidos externamente.
4. Não renomear contratos públicos existentes sem versionamento e plano de migração.
5. Migrar o legado somente quando o componente for alterado e houver cobertura de testes.
6. Registrar exceções no arquivo `governance/idioma/excecoes.json`, com justificativa e responsável.
7. Não traduzir dados de telemetria que sejam contratos de integração; a apresentação ao usuário deve permanecer em português.

## Exemplos

| Contexto | Recomendado | Evitar em artefatos novos |
|---|---|---|
| Domínio | `Demanda`, `Parecer`, `FilaAtendimento` | `Request`, `Opinion`, `ServiceQueue` |
| Operação | `reservarDemanda` | `reserveRequest` |
| Estado | `EM_ATENDIMENTO` | `IN_PROGRESS` |
| API nova | `/api/demandas/{id}/reservar` | `/api/requests/{id}/reserve` |
| Registro | `Demanda reservada com sucesso` | `Request reserved successfully` |

## Exceções técnicas

Podem permanecer no idioma original: HTTP, JSON, SQL, OAuth, OpenAPI, Dockerfile, `Content-Type`, `access_token`, `correlation_id`, palavras reservadas de linguagens e nomes oficiais de produtos.

## Adoção progressiva

1. Estágio consultivo: inventário e avisos, sem bloquear.
2. Estágio controlado: bloqueio apenas para novos termos de domínio já mapeados.
3. Estágio governado: indicadores de adesão, exceções com validade e dívida legada acompanhada.
