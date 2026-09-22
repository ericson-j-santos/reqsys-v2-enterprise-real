# IA ML Lab — Trilha Google Drive

Pacote de curadoria técnica derivado da análise da pasta de estudos de Inteligência Artificial, Machine Learning, LLMs, RAG e Agentes.

## Objetivo

Transformar a trilha de materiais em um laboratório técnico versionado, reaproveitável no ReqSys e publicável como portfólio.

## Escopo inicial

- Organizar o mapa de estudo de IA e Machine Learning.
- Registrar vínculo com aplicações do ReqSys.
- Definir plano do projeto final com Adult Income Dataset.
- Estabelecer critérios mínimos de governança, rastreabilidade e reprodutibilidade.
- Evitar versionar arquivos residuais `Zone.Identifier`.

## Estrutura proposta

```text
ia-ml-lab/
├── README.md
├── CHANGELOG.md
└── docs/
    ├── trilha-estudo.md
    ├── aplicacoes-reqsys.md
    └── projeto-final-adult-income.md
```

## Status

| Dimensão | Estado |
|---|---|
| Curadoria inicial | Implementada |
| Integração com ReqSys | Planejada e documentada |
| Pipeline produtivo de ML | Pendente |
| Notebooks versionados | Pendente |
| CI específico | Pendente |
| XAI/explicabilidade | Planejada |

## Próximos incrementos

1. Criar notebook limpo do projeto final.
2. Adicionar pipeline Python reprodutível em `src/`.
3. Adicionar testes mínimos para pré-processamento e métricas.
4. Adicionar SHAP ou alternativa de explicabilidade.
5. Publicar relatório técnico em documentação viva.
