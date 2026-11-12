# Trilha A — Runtime público DEV no PC24x7 (sem Fly.io)

## Operação atual
GitHub Pages fornece a entrada estável do ambiente DEV; um localizador com assinatura Ed25519 anuncia a rota temporária Cloudflare; o destino pretendido é PC24x7. Fonte versionada: `infra/public-access-urls.json`. **O arquivo é declaração de arquitetura, não prova de que o computador ou sistema está acessível neste instante.**

## Validação segura de configuração
No checkout isolado e governado:

```text
python -m unittest discover -s tests -p 'test_dev_runtime_manifest.py' -v
python scripts/validate_dev_runtime_manifest.py
python scripts/trilha_a_runtime_publico.py
python scripts/trilhas_padrao_ouro.py
```

Os comandos validam estrutura e geram relatórios no checkout. Não usam Docker, Fly.io, ODBC, segredos ou rede. O validador antigo `scripts/runtime_public_validator.py` permanece aposentado e não é executado.

## Resultados e limitações
- `passed_with_warnings`: manifesto DEV íntegro, mas `operational_status=config_only`, `physical_e2e_verified=false`, `signed_locator_verified=false` e `http_probe_performed=false`. Não equivale a liberação operacional.
- `failed`: manifesto inválido, URL Fly ou insegura, assinatura de locator não configurada, destino errado, HML/PROD promovida, resultado incompleto ou caminho ausente.
- Relatórios: `audit/trilha-a/trilha-a-runtime-publico-report.json` e `audit/trilhas/trilhas-padrao-ouro-report.json`.

## Próxima validação operacional
Runtime Platform deve usar a fonte externa autenticada do localizador e Gateway para comprovar assinatura, idade, identidade física, rota real, health, SHA e consistência. Não utilizar somente HTTP 200 como prova de funcionamento. E2E entre Noteri e Desktop requer duas máquinas, lease e checkpoint duráveis; continua no escopo da PR #3141. Sem merge, deploy ou mudança física automática.

## Rastreabilidade
Issue [#3145](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3145), arquitetura [ADR-047](../adr/ADR-047-pc24x7-public-ingress.md) e runbook [PC24x7 DEV](pc24x7-piloto-dev.md). Observações históricas sobre Fly.io na ADR-036 não reativam o provedor.
