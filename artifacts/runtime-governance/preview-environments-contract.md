# Preview Environments Contract

Atualizado em: 2026-06-27

## Objetivo

Definir o contrato mínimo para ambientes efêmeros por PR, permitindo validar frontend, backend, runtime smoke e evidências operacionais antes de merge.

## Problema que resolve

CI verde não garante que o incremento esteja navegável, responsivo ou coerente no runtime público. O preview environment adiciona uma camada de evidência antes da integração definitiva.

## Escopo do incremento

Artefato governado para padronizar a criação futura de previews sem acoplar este PR a infraestrutura produtiva.

## Contrato mínimo por PR

| Recurso | Obrigatório | Observação |
|---|---:|---|
| URL de preview | Sim | Deve ser efêmera e vinculada ao número do PR |
| Smoke backend | Sim | Health endpoint e contratos críticos |
| Smoke frontend | Sim | Build, rota inicial e renderização básica |
| Runtime evidence | Sim | Resultado JSON armazenável em artifact |
| Correlation ID | Sim | Rastreabilidade de execução |
| Expiração | Sim | Evitar custo e lixo operacional |
| Ambiente produtivo | Não | Preview não pode alterar produção |

## Modelo de evidência

```json
{
  "pr": 0,
  "environment": "preview",
  "url": "https://reqsys-pr-000-preview.example",
  "status": "green",
  "checks": {
    "backend_health": "green",
    "frontend_render": "green",
    "runtime_smoke": "green",
    "contracts": "green"
  },
  "expires_at": "2026-06-28T00:00:00Z",
  "correlation_id": "preview-pr-000"
}
```

## Regras de governança

- Preview não deve executar migração destrutiva.
- Preview não deve consumir secrets produtivos.
- Preview não deve gravar dados reais.
- Preview deve produzir artifact objetivo.
- Falha de preview bloqueia merge quando o PR altera runtime, frontend ou contrato público.

## Critérios de aceite

- Contrato de preview versionado.
- Separação explícita entre preview e produção.
- Evidência JSON padronizada.
- Preparado para GitHub Actions/Fly.io sem exigir mudança imediata de infraestrutura.

## Próximo incremento técnico

Criar workflow `.github/workflows/preview-environment-contract.yml` inicialmente em modo dry-run para gerar artifact JSON sem publicar infraestrutura real. Depois evoluir para Fly.io preview app quando o contrato estiver estável.
