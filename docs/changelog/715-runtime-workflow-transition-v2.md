# 715 — Runtime Workflow Transition v2

## Contexto

Reaplica a consolidação do Runtime Core para transição de requisitos em branch limpa baseada na `main`, evitando conflito identificado no PR anterior.

## Escopo

- Acoplar publicação de evento governado na transição de requisitos.
- Preservar rota legada como fallback estrutural.
- Validar path real registrado pelo `APIRouter` com prefixo `/api/requisitos`.

## Evidência esperada

- Testes backend para ordenação de rotas.
- CI governado verde antes de merge.
- Merge-readiness sem branch behind ou conflito.
