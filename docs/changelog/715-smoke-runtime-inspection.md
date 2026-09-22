# 715 — Smoke Runtime Inspection

## Contexto

Após o merge da inspeção operacional do Runtime Core de requisitos, este incremento adiciona a rota ao smoke público governado para produzir evidência automática pós-merge/deploy.

## Entrega

- Inclui `/api/requisitos/runtime/inspection` nos endpoints opcionais do `runtime_production_smoke_governed.py`.
- Preserva os endpoints obrigatórios atuais sem aumentar risco de bloqueio de deploy.
- Amplia a leitura de status de envelope para `data.health.status`, mantendo compatibilidade com `data.status` e `status`.

## Risco

Baixo. Incremento aditivo no smoke público, sem alterar código produtivo da API.

## Próximo incremento recomendado

Publicar o resultado do endpoint no snapshot executivo de runtime/evidência operacional.
