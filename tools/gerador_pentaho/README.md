# Gerador — Fluxo de criação de dossiê (Pentaho)

Empacotador CLI para a aplicação de treinamento `pacote/`: um fluxo sintético de
criação de dossiê (autenticar → criar dossiê → validar resposta → evidenciar),
reproduzido tanto em Node.js quanto como job/transformações Pentaho Data
Integration 7.1+ (Kitchen/Spoon). Ver [`pacote/README.md`](pacote/README.md)
para como executar a aplicação gerada.

## Por que um gerador, se o pacote já está versionado?

O código-fonte de verdade é o diretório [`pacote/`](pacote/), versionado
arquivo a arquivo (revisável em PR, diffável, testável — nenhum blob binário
no histórico). Este script (`gerador_solucao_completa.py`) serve apenas para
**distribuir** esse diretório fora do controle de versão, quando necessário
(ex.: anexar a um chamado, entregar a quem só tem acesso ao ambiente Pentaho
e não ao repositório).

## Uso

Listar o conteúdo do pacote sem gerar nada:

```bash
python tools/gerador_pentaho/gerador_solucao_completa.py --dry-run
```

Gerar a aplicação em um diretório:

```bash
python tools/gerador_pentaho/gerador_solucao_completa.py --output /tmp/dossie-pentaho --force
```

Gerar e também rodar os testes automatizados (Node.js 18+ necessário):

```bash
python tools/gerador_pentaho/gerador_solucao_completa.py --output /tmp/dossie-pentaho --force --run-tests
```

Gerar também um ZIP portátil para distribuição:

```bash
python tools/gerador_pentaho/gerador_solucao_completa.py --output /tmp/dossie-pentaho --force --zip /tmp/dossie-pentaho.zip
```

## Controles de padrão ouro aplicados a este tool

- fonte de verdade versionada (sem payload base64 embutido nem SHA-256 fixo
  para validar contra um blob congelado);
- dados exclusivamente sintéticos em `pacote/` (ADR-002/LGPD) — sem segredo,
  CPF, e-mail real ou endpoint interno (ver `docs/servicos/gerador-pentaho-dossie.md`
  para o resultado da varredura);
- CLI com `--dry-run`, `--force` e `--run-tests`, no mesmo padrão dos demais
  geradores do repositório (`tools/geradores/gerar_servicos_email_teams.py`);
- teste automatizado (`tests/test_gerador_pentaho.py`) cobrindo listagem,
  geração de diretório, geração de ZIP e falha esperada em destino existente
  sem `--force`;
- validado em CI (`.github/workflows/gerador-pentaho-dossie-validation.yml`)
  a cada alteração em `tools/gerador_pentaho/**`.

## Cobertura de testes do fluxo (`pacote/testes/fluxo.test.js`)

Priorizada por Pareto: os 5 estados finais documentados em
[`pacote/README.md`](pacote/README.md#linguagem-ubíqua-e-estados) e os
critérios de aceite de retentativa/timeout de
[`pacote/docs/mapeamento-pentaho.md`](pacote/docs/mapeamento-pentaho.md#critérios-de-aceite)
concentravam o maior risco de regressão silenciosa com o menor número de
casos — cada teste abaixo cobre pelo menos um estado final ou um critério de
aceite antes não verificado:

| Estado final / critério | Teste |
| --- | --- |
| `DOSSIÊ_CRIADO` | criação com sucesso |
| `CRIAÇÃO_RECUSADA` | recusa de regra de negócio; e não repetição automática em 4xx |
| `RESPOSTA_INVÁLIDA` | 5xx persistente após esgotar tentativas |
| `AUTENTICAÇÃO_RECUSADA` | credencial inválida |
| `FALHA_TÉCNICA` | campo obrigatório ausente (sem chamada de rede); e conexão recusada |
| retentativa em 5xx intermitente | sucede antes de esgotar `MAX_TENTATIVAS` |
| não repetir em 4xx | erro 4xx chama a API de criação exatamente uma vez |
| respeitar `MAX_TENTATIVAS` | 5xx persistente chama exatamente `MAX_TENTATIVAS` vezes |

Executar: `node --test pacote/testes/fluxo.test.js` (a partir de
`tools/gerador_pentaho/`, ou via `--run-tests` do CLI). O `pacote/package.json`
(`"type": "commonjs"`) existe só para isolar essa árvore da configuração
`"type": "module"` da raiz do repositório — sem ele, `node --test` executado
de dentro do repo (fora do gerado por `--output`) falha com
`ReferenceError: require is not defined`.

## Estrutura

```text
tools/gerador_pentaho/
├── gerador_solucao_completa.py   # CLI empacotador
├── README.md                     # este arquivo
└── pacote/                       # fonte de verdade da aplicação gerada
    ├── README.md                 # como executar a aplicação (Node.js e Pentaho)
    ├── CHANGELOG.md
    ├── package.json              # type: commonjs (isola de "type": "module" da raiz)
    ├── .env.example
    ├── dashboard.html
    ├── docs/
    ├── exemplos/
    ├── pentaho/                  # job (.kjb) e transformações (.ktr)
    ├── src/                      # fluxo Node.js equivalente
    └── testes/
```
