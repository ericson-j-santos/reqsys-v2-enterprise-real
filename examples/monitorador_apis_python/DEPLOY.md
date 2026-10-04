# Deploy do Monitorador de APIs Python

## Estado

| Item | Evidenciado | Alvo |
|---|---:|---:|
| FastAPI | VERDE | VERDE |
| Endpoint health | VERDE | VERDE |
| Dashboard HTML | VERDE | VERDE |
| Dockerfile | VERDE | VERDE |
| Render blueprint | VERDE | VERDE |
| Railway config | VERDE | VERDE |
| URL publica executavel | PENDENTE | VERDE apos conectar provedor |

## Execucao local

```bash
cd examples/monitorador_apis_python
pip install -r requirements.txt
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Rotas:

- `/`
- `/health`
- `/api/monitorar`
- `/api/resultados`
- `/dashboard`
- `/docs`

## Docker

```bash
cd examples/monitorador_apis_python
docker build -t monitorador-apis-python .
docker run --rm -p 8000:8000 monitorador-apis-python
```

## Render

1. Criar novo Web Service.
2. Conectar o repositorio.
3. Usar Docker runtime.
4. Definir contexto `examples/monitorador_apis_python`.
5. Definir health check `/health`.

## Railway

1. Criar novo projeto a partir do GitHub.
2. Selecionar este repositorio.
3. Usar o Dockerfile do projeto.
4. Definir health check `/health`.

## Restricoes

- A URL publica depende de autenticacao no provedor de deploy.
- Nao ha secrets obrigatorios nesta versao.
- SQLite local em container nao deve ser usado como armazenamento persistente definitivo em producao.
- Para producao real, migrar historico para banco gerenciado.
