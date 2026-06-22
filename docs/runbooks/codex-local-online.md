# Runbook — Codex Local Online

## Objetivo

Operar e validar a aplicação online de análise governada integrada ao ReqSys.

## URL esperada

```text
https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/
```

## Validação

1. Abrir a URL publicada.
2. Confirmar carregamento do título `ReqSys Codex Online`.
3. Executar análise em modo demonstração.
4. Confirmar retorno com `correlation_id`.
5. Gerar payload ReqSys.
6. Validar que nenhum dado sensível foi informado.

## Falhas comuns

| Sintoma | Causa provável | Ação |
|---|---|---|
| 404 Pages | Pages não habilitado | Habilitar GitHub Pages por Actions |
| Deploy não executa | PR ainda não mesclado | Executar merge ou workflow_dispatch |
| CORS no backend | Origem não permitida | Liberar apenas domínio Pages |
| Bloqueio de conteúdo | Possível dado sensível | Remover dado sensível |

## Critério de pronto

- Workflow verde.
- Pages publicado.
- Aplicação acessível online.
- Payload ReqSys gerado.
- ADR e runbook versionados.
