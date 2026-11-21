# ReqSys Control — Reconciliação governada (feature)

Origem: solicitação explícita de 21/11/2026; usar issue canônica de inventário [#3149](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3149), vínculos [#1686](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1686) (Redmine) e [#3126](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3126) (piloto). Esta mudança é uma **feature assistida**: a visão cruzada de fontes ainda não existe no ReqSys Control da main@a05e64bbc58a15314b42cfa9314f1d415535b05b; não é reparo de falha reproduzida. source_mode=assisted; model_calls=0 (sem Builder externo).

## Objetivo e aceite
1. Uma única entrada no menu do painel ReqSys Control existente; **não criar ou publicar outro site**.
2. Exibir campos e divergências Redmine/TODO/GitHub/host, gates, SHA, evidências, dependências e histórico; dados de demonstração rotulados.
3. Integrar arquivo estático em iframe com sandbox sem allow-same-origin; nenhuma API externa, segredo, evento, dispatch, push, merge ou execução física.
4. Positivos: navegação, filtro, criação/edição local com confirmação, exportação, responsividade e classificação de alertas.
5. Negativos: recusa de confirmação sem mudança, segredo suspeito, JSON duplicado/inválido, XSS e bloqueio de execução sem prova.
6. Replay sem duplicação; estado local não é TODO Global nem comprovante de origem. Sem autenticação de provedores nesta etapa.
7. Readback de bytes/commit/SHA das duas fontes Git depois de push, com divergência de SHAs explicitada.
8. Nenhum merge, MR/PR, deploy ou site novo antes de gates e autorização específica. Manter a operação real BLOQUEADA até RBAC, E2E e readback independentes.

Regras: 58dcd4200f412a866278027ba9e433439a03f3b3; base GitHub a05e64bbc58a15314b42cfa9314f1d415535b05b. Custo incremental máximo R$ 0,00; sem Docker e sem automação GUI. Autorizações para push da versão isolada: conversa em 21/11/2026. Não equivalem a autorização de merge/deploy.
