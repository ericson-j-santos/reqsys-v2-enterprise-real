# Catálogo Governado ReqSys — protótipo HTML de referência

> **NÃO É A SOLUÇÃO OFICIAL. NÃO PUBLICAR, FAZER MERGE OU IMPLANTAR AUTOMATICAMENTE.**

## Origem e finalidade

Snapshot do HTML autocontido criado em 13/11/2026 para registrar e comparar sites, códigos e soluções relacionados ao ReqSys. Está guardado **somente para referência e rastreabilidade**, sem substituir a aplicação original, a issue canônica nem o desenvolvimento integrado.

- Fonte do inventário e decisões: [issue #3149](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3149).
- Implementação integrada que deve ser priorizada: branch `feat/catalogo-aplicacoes-3149-20261113`, componentes `frontend/src/components/CatalogoAplicacoes.vue` e `frontend/src/data/catalogoAplicacoes.js` — ainda não aprovada para integração operacional.
- Aplicação ReqSys original: `frontend/` na `main`; preservar.
- Fonte histórica deste protótipo: `index.html` neste diretório; SHA-256 da versão original: `13d24920162f141460ad2c319b797ac3b119663de128ee0ce5bc272d8b275b91`.

## Limitações e proteção contra falso positivo

1. Funciona como arquivo local e **não sincroniza** GitHub, TODO Global, GitLab, URLs, hosts nem produção.
2. Os registros e comprovações são preenchidos manualmente; nome, URL HTTPS, SHA com 40 caracteres ou campo marcado “sim” **não representam validação independente**.
3. LocalStorage é armazenamento do navegador, **não checkpoint durável compartilhado**; exportar JSON e armazenar de forma governada sem dados pessoais desnecessários.
4. Não há RBAC/autenticação própria. Não inserir segredos, links privados com tokens ou dados protegidos pela LGPD.
5. Nenhuma integração, exclusão, push, merge, deploy, autorização administrativa ou envio de e-mail ocorre a partir do arquivo.
6. Custo incremental da execução do arquivo no navegador: nenhuma nova infraestrutura contratada; custos de eventual hospedagem **não foram auditados**.

## Validação deste snapshot

- Sintaxe JavaScript separada: `node --check` **passou** em 13/11/2026 no ambiente de artefatos.
- Inspeção estática: um script inline, sem script externo, sem `eval`, sem carregamento externo encontrado.
- Teste de interação no Chromium: **bloqueado pela política do navegador** (`net::ERR_BLOCKED_BY_ADMINISTRATOR` ao abrir `file://`); **não é E2E aprovado**.
- URL implantada, acesso, host físico, leitura independente de operação e uso real: **não comprovados**.

## Condição para evolução

Evoluir a implementação já existente no Painel de Projetos, após o contrato SDD, `READY_FOR_PR` no SHA atual, testes positivos e negativos, Validator independente, autorização específica e E2E no destino. Este snapshot permanece histórico e não deve criar nova rota oficial.

Referências: regras globais 1.6.21 (`58dcd4200f412a866278027ba9e433439a03f3b3`) e ReqSys `main@a05e64bbc58a15314b42cfa9314f1d415535b05b` na data-base.
