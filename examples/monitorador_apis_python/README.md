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
| Testes pytest | VERDE | VERDE |
| CI GitHub Actions | VERDE após execução do PR | VERDE |

## Execução local

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

## Testes

```bash
pytest
pytest --cov=app --cov-report=term-missing --cov-fail-under=85
```

## Saídas geradas

- `data/monitoramento.db`
- `logs/monitorador.log`
- `reports/relatorio_monitoramento.html`

## Observação sobre publicação online

Este incremento deixa o código e a documentação disponíveis online no GitHub. Para executar como serviço público com URL própria, o próximo incremento recomendado é empacotar uma API FastAPI e publicar em Fly.io, Render ou Railway.
