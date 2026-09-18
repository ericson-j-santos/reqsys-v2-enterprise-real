# copilot-memory-core

Núcleo portátil da solução de memória persistente para Copilot, Planner e Excel/SharePoint.

## Características

- zero dependências externas em tempo de execução;
- não depende de ReqSys, FastAPI, SQLAlchemy ou Microsoft 365;
- hash SHA-256 determinístico;
- normalização de snapshots;
- prevenção de reprocessamento idêntico;
- decisão de atualização Planner;
- detecção de conflito quando há atualização local pendente;
- adequado para empacotamento `.whl` e uso offline.

## Instalação

Dentro desta pasta:

```bash
python -m build
pip install dist/copilot_memory_core-1.0.0-py3-none-any.whl
```

## Uso

```python
from copilot_memory_core import content_hash, montar_snapshot

snapshot = montar_snapshot({
    'planner_task_id': 'task-123',
    'assunto': 'Exemplo',
    'planner_percentual': 25,
})
print(content_hash(snapshot))
```

Persistência, API, SQL Server, Planner, Power Automate e Excel são adaptadores externos ao núcleo.
