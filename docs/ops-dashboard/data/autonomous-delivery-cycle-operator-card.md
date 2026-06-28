# Operator Card — Autonomous Delivery Cycle

## Para ativar em um PR

Adicionar labels:

```text
merge-queue:eligible
cycle:auto-merge-approved
```

## Para pausar

Remover:

```text
cycle:auto-merge-approved
```

## Para validar sem risco

Executar workflow com:

```text
dry_run=true
```

## Para executar merge governado

Executar workflow com:

```text
dry_run=false
```

A execução real ainda depende de CI verde e labels obrigatórias.
