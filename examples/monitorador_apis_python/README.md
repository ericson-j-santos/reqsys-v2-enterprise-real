# Monitorador de APIs em Python

Projeto prático para treinar Python com foco profissional e base reutilizável para observabilidade simples.

## Funcionalidades

| Item | Estado evidenciado | Estado alvo |
|---|---:|---:|
| Async/await | VERDE | VERDE |
| Retry com backoff | VERDE | VERDE |
| Cache TTL | VERDE | VERDE |
| Persistência SQLite | VERDE | VERDE |
| Logs estruturados | VERDE | VERDE |
| Relatório HTML | VERDE | VERDE |
| FastAPI | VERDE | VERDE |
| Endpoint `/health` | VERDE | VERDE |
| Dashboard HTML runtime | VERDE | VERDE |
| Dockerfile | VERDE | VERDE |
| Render/Railway config | VERDE | VERDE |
| Testes pytest | VERDE | VERDE |
| CI GitHub Actions | VERDE após execução do PR | VERDE |
| URL pública executável | AMARELO | VERDE após deploy no provedor |

## Execução local CLI

```bash
cd examples/monitorador_apis_python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Linux/macOS:

```bash
source .venv/bin/activate
```

## Execução web FastAPI

```bash
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
docker build -t monitorador-apis-python .
docker run --rm -p 8000:8000 monitorador-apis-python
```

## Testes

```bash
pytest
pytest --cov=app --cov-report=term-missing --cov-fail-under=85
```

## Saídas geradas

- `data/monitoramento.db`
- `logs/monitorador.log`
- `reports/relatorio_monitoramento.html`

## Deploy

Arquivos disponíveis:

- `Dockerfile`
- `render.yaml`
- `railway.json`
- `DEPLOY.md`

A URL pública depende da conexão do repositório a um provedor de deploy autenticado, como Render ou Railway.
