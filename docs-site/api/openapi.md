# OpenAPI / Swagger

> **Versão:** `0.6.0`  
> **Escopo:** contrato canônico gerado pelo FastAPI runtime para documentação viva, Swagger/OpenAPI e integrações assíncronas.

## Artefato oficial

```text
docs-site/assets/openapi/reqsys-runtime-openapi-v0.6.0.json
```

Quando publicado via GitHub Pages, o arquivo deve ficar disponível em:

```text
assets/openapi/reqsys-runtime-openapi-v0.6.0.json
```

## Fonte canônica

O contrato `v0.6.0` é gerado a partir do runtime executável:

```text
runtime/scripts/export_openapi.py
```

Validação obrigatória contra drift:

```bash
cd runtime
python scripts/export_openapi.py --check
```

## Objetivo

Formalizar os contratos reais do runtime para permitir:

- criação assíncrona de jobs;
- consulta de status por `job_id`;
- health/readiness operacional;
- analytics básicos de fila/jobs;
- uso em Swagger/OpenAPI;
- consumo por Power Automate e APIs corporativas;
- versionamento rastreável de payloads e responses.

## Endpoints documentados

| Método | Endpoint | Finalidade | Tag |
|---|---|---|---|
| `GET` | `/health` | Health check básico | `runtime` |
| `GET` | `/api/runtime/health` | Health/readiness do runtime | `runtime` |
| `GET` | `/api/runtime/analytics` | Métricas operacionais | `runtime` |
| `POST` | `/api/jobs` | Criar job assíncrono | `jobs` |
| `GET` | `/api/jobs/{job_id}` | Consultar status do job | `jobs` |

## Base URL DEV

```text
https://reqsys-api.fly.dev
```

## Contrato de governança

| Item | Regra |
|---|---|
| Versão | Todo contrato canônico deve declarar `0.6.0` nesta versão |
| Fonte | O contrato canônico deve ser gerado pelo FastAPI runtime |
| Drift | `runtime/scripts/export_openapi.py --check` deve passar no CI |
| Correlação | Toda operação assíncrona deve carregar `correlation_id` |
| Segurança | Não registrar dados sensíveis em claro |
| Compatibilidade | Mudanças incompatíveis exigem nova versão maior |
| Evidência | Alterações devem passar pelos testes do runtime e pelo `mkdocs build --strict` |

## Uso local opcional

```bash
python -m json.tool docs-site/assets/openapi/reqsys-runtime-openapi-v0.6.0.json
```

## Próximo incremento natural

Adicionar adapter Redis ou Azure Service Bus sem alterar o contrato HTTP canônico.
