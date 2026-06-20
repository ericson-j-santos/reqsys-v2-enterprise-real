# 2026-06-20 — REQSYS-OPER-005 — Riscos

## Riscos identificados

- Branch pode precisar de sincronização com `main` antes do merge.
- Tela inicial depende do endpoint backend estar disponível no mesmo domínio ou via proxy configurado.
- Coleta real de sinais operacionais ainda não foi implementada.
- Persistência histórica ainda não foi implementada.

## Mitigações

- Manter PR em draft até CI verde.
- Não considerar a primeira fatia como solução completa.
- Evoluir por incrementos com testes e evidências.

Refs #46
