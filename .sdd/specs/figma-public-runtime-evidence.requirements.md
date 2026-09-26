# Evidência pública Figma/GitHub — Requisitos

## Objetivo

Estender o validador público somente leitura para registrar evidência dos endpoints Figma/GitHub com rastreabilidade por `correlation_id`, sem disparar sincronização, alterar configuração, criar segredos ou tocar produção.

## Requisitos

1. A coleta opcional deve consultar apenas `GET /v1/integracoes/figma-github/config` e `GET /v1/integracoes/figma-github/status`.
2. O validador deve preservar o `correlation_id` retornado pelo envelope quando disponível.
3. Na ausência do campo no envelope, o validador pode usar cabeçalhos de rastreabilidade suportados.
4. O fluxo não pode executar `POST /sync`.
5. Falha de evidência opcional não pode ser convertida em sucesso fabricado.
6. O harness de teste que carrega o validador por `importlib` deve registrar o módulo em `sys.modules` antes da execução, preservando compatibilidade com `dataclass` no Python 3.12.

## Critérios de aceite

1. `tests/test_validate_public_runtime_figma_evidence.py` comprova a coleta dos dois endpoints Figma/GitHub.
2. O artifact preserva o `correlation_id` do envelope ou o identificador equivalente permitido.
3. O teste comprova que nenhum `POST /sync` é emitido.
4. Nenhum segredo, deploy ou alteração de produção faz parte deste incremento.
5. O carregamento dinâmico do módulo passa no Python 3.12 sem `AttributeError` de `dataclass`.
