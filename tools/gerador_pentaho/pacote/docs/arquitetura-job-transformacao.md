# Arquitetura do job e da transformação

## Responsabilidades

| Camada | Artefato | Responsabilidade |
|---|---|---|
| Orquestração | `JB_TREINO_CRIAR_DOSSIES` | início, validação, execução e término governado |
| Pré-condição | `TR_VALIDAR_CONFIGURACAO` | falhar cedo quando configuração obrigatória estiver ausente |
| Negócio | `TR_CRIAR_DOSSIES_TREINO` | autenticar, criar dossiê, classificar e evidenciar |
| Dependência | `servidor-simulado.js` | reproduzir contratos HTTP sem rede corporativa |

## Ordem de execução

1. Iniciar `servidor-simulado.js`.
2. Executar o job com `Kitchen` ou abri-lo no Spoon.
3. O job valida parâmetros.
4. A transformação lê `demandas.csv`.
5. Cada demanda recebe correlação e chave idempotente.
6. A transformação autentica e mantém o token apenas em memória.
7. A chamada de criação retorna sucesso ou recusa sintética.
8. A evidência sanitizada é gravada em `saida/evidencias_pentaho.csv`.

## Limite conhecido

Os XMLs foram construídos para a família Pentaho Data Integration 7.1. O ambiente desta entrega não contém o Spoon/Kitchen 7.1; portanto, foram validados estruturalmente como XML, mas a abertura visual e a execução no motor Pentaho permanecem como validação de homologação.

