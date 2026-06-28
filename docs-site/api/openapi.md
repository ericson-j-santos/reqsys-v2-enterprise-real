# OpenAPI / Swagger

> **Versão:** `0.3.0`  
> **Escopo:** contrato versionado para documentação viva, Swagger/OpenAPI e prática Power Automate GET/POST.

## Artefato oficial

```text
docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json
```

Quando publicado via GitHub Pages, o arquivo deve ficar disponível em:

```text
assets/openapi/reqsys-runtime-openapi-v0.3.0.json
```

## Objetivo

Formalizar os contratos mínimos de runtime e requisitos mockados para permitir:

- consulta GET de requisito por identificador;
- recebimento POST de requisito;
- uso em Swagger/OpenAPI;
- importação em ferramentas como Postman;
- consumo por Power Automate;
- versionamento de payloads e responses.

## Endpoints documentados

| Método | Endpoint | Finalidade | Tag |
|---|---|---|---|
| `GET` | `/health` | Health check básico | `runtime` |
| `GET` | `/api/runtime/health` | Health check runtime | `runtime` |
| `GET` | `/api/requisitos/{id}` | Consultar requisito mockado | `requisitos` |
| `POST` | `/api/requisitos` | Receber requisito mockado | `requisitos` |

## Base URL DEV

```text
https://reqsys-api.fly.dev
```

## Contrato de governança

| Item | Regra |
|---|---|
| Versão | Todo contrato deve declarar `0.3.0` nesta versão |
| Correlação | Toda resposta operacional deve carregar `correlation_id` |
| Segurança | Não registrar dados sensíveis em claro |
| Compatibilidade | Mudanças incompatíveis exigem nova versão maior |
| Evidência | Alterações devem passar pelo `mkdocs build --strict` |

## Uso local opcional

```bash
python -m json.tool docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json
```

## Próximo incremento natural

Adicionar renderização interativa Swagger UI ou Redoc sem quebrar o fallback corporativo/offline.
