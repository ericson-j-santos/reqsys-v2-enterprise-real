# Servidor automático de fluxogramas, diagramas e BPMN

## Objetivo

Evoluir o módulo de Arquitetura Viva do ReqSys para receber uma definição de processo estruturada e gerar, de forma determinística:

- fluxograma Mermaid;
- BPMN 2.0 XML compatível com modeladores BPMN;
- hash SHA-256 do conjunto de artefatos;
- métricas de nós, conexões e decisões;
- rastreabilidade por `X-Correlation-Id`.

## Endpoints

| Método | Endpoint | Resultado |
| --- | --- | --- |
| `POST` | `/v1/diagramas/automatico/gerar` | JSON consolidado com Mermaid e BPMN |
| `POST` | `/v1/diagramas/automatico/mermaid` | Texto Mermaid |
| `POST` | `/v1/diagramas/automatico/bpmn` | Arquivo BPMN 2.0 XML |
| `GET` | `/v1/diagramas/automatico/contrato` | Contrato e capacidades do serviço |
| `GET` | `/v1/diagramas/health` | Saúde e capacidades do módulo |

## Exemplo de requisição

```json
{
  "process_id": "approval_flow",
  "name": "Aprovação de requisito",
  "version": "1.0.0",
  "nodes": [
    {"id": "start", "name": "Demanda recebida", "type": "start"},
    {"id": "analyze", "name": "Analisar requisito", "type": "task"},
    {"id": "approved", "name": "Requisito aprovado?", "type": "decision"},
    {"id": "publish", "name": "Publicar backlog", "type": "task"},
    {"id": "adjust", "name": "Solicitar ajustes", "type": "task"},
    {"id": "end", "name": "Processo finalizado", "type": "end"}
  ],
  "edges": [
    {"source": "start", "target": "analyze"},
    {"source": "analyze", "target": "approved"},
    {"source": "approved", "target": "publish", "label": "sim"},
    {"source": "approved", "target": "adjust", "label": "não"},
    {"source": "publish", "target": "end"},
    {"source": "adjust", "target": "end"}
  ]
}
```

## Validações de governança

O serviço rejeita definições com:

- identificadores duplicados;
- origem ou destino inexistente;
- autorreferência;
- quantidade diferente de um evento inicial;
- ausência de evento final;
- fluxo de entrada no evento inicial;
- fluxo de saída em evento final;
- nós inacessíveis a partir do início;
- mais de 500 nós ou 1.000 conexões por requisição.

## Execução local

```bash
cd backend
pytest -q tests/test_automatic_diagram_server.py
uvicorn app.main:app --reload
```

A documentação OpenAPI fica disponível em `/docs` e o painel existente em `/v1/diagramas/dashboard`.

## Próximos incrementos

1. Persistência versionada dos processos e artefatos em banco ou object storage.
2. BPMN Diagram Interchange (`BPMNShape` e `BPMNEdge`) para coordenadas visuais editáveis.
3. Conversão automática de requisitos, histórias e workflows ReqSys em definições de processo.
4. Exportação SVG/PNG por worker isolado, sem executar conteúdo arbitrário no processo principal.
5. Editor visual integrado ao frontend com validação e comparação de versões.
