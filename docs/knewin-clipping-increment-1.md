# Knewin Clipping — Incremento 1

## Objetivo

Formalizar o primeiro núcleo determinístico do fluxo observado no vídeo: normalização dos resultados de clipping, classificação inicial de relevância, mapeamento governado de Tier/Unidade e chave de idempotência.

## Entrada mínima

- `date`
- `vehicle`
- `media`
- `title`
- `url`

Campos opcionais: `snippet`, `origin`, `subject`, `source_person`.

## Saída

O serviço gera um `ClippingRecord` com os nove campos de negócio e metadados técnicos de relevância, idempotência e necessidade de revisão.

## Regras deste incremento

1. URL é canonizada e parâmetros de rastreamento conhecidos são descartados.
2. `idempotency_key = sha256(url_canonica|data|veiculo)`.
3. Referência explícita a professor/coordenador/especialista da FECAP pode ser incluída automaticamente.
4. Referência biográfica incidental pode ser excluída automaticamente.
5. Demais referências à FECAP vão para `review`; nenhuma inferência ambígua é tratada como fato.
6. Tier e unidade de negócio vêm somente de cadastros fornecidos ao serviço. Valor desconhecido nunca é inventado.
7. Origem e assunto ausentes mantêm `requires_review=true`.

## Fora do escopo

- autenticação e coleta real no Knewin;
- escrita em Excel/SharePoint;
- inferência por IA de assunto/origem;
- persistência definitiva dos cadastros de Tier e Unidade.

## E2E alvo do próximo incremento

`Knewin DEV/sessão autorizada -> coleta de resultado -> normalização -> deduplicação -> gravação em destino de homologação -> leitura independente do destino`.

Casos obrigatórios: relevante incluído, incidental excluído, ambíguo em revisão e reprocessamento idempotente sem duplicidade.
