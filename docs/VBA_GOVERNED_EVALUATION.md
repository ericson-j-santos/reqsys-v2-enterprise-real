# Avaliação governada de VBA

O ReqSys oferece um fluxo aditivo para avaliar um módulo VBA exportado sem abrir
Office nem executar a macro:

1. reutiliza a análise estática existente;
2. bloqueia literais de segredo antes de emitir qualquer pacote;
3. normaliza a fonte e aplica `Option Explicit` de forma idempotente;
4. reanalisa a candidata e bloqueia qualquer deriva na projeção estática;
5. gera um ZIP determinístico, versionado e verificável por SHA-256.

O endpoint administrativo é:

```text
POST /api/requisitos/legado/vba/avaliar-versao-controlada
multipart/form-data: arquivo=<modulo.bas>, versao=<SemVer>
```

Somente `.bas` exportado é aceito para transformação nesta primeira versão.
Arquivos `.cls`, `.frm`, `.vba`, `.txt` e contêineres Office continuam disponíveis
no endpoint de análise estática, mas são recusados neste fluxo com o código
`VBA_GOVERNED_TRANSFORMATION_REQUIRES_EXPORTED_BAS`.

## Garantias e limites

O fluxo comprova apenas que a projeção produzida pelo analisador estático se
manteve após a transformação conservadora. O resultado sempre declara:

```text
candidate_status = PROPOSED_NOT_RELEASED
static_preservation = PASS
functional_equivalence = NOT_PROVEN
compile_validation = NOT_RUN
dynamic_validation = FUTURE_REQUIRED
release_allowed = false
```

`Option Explicit` pode revelar variáveis implícitas durante uma compilação futura.
Por isso, o ReqSys não classifica a candidata como Versão Mínima Controlada, não
afirma equivalência funcional e não injeta genericamente tratamento de erros,
logging ou validações de parâmetros que poderiam alterar regras de negócio.

Nenhum processo Office, COM, VBA, shell ou subprocesso é iniciado. A fonte
normalizada é incluída no pacote retornado, mas a fonte e o pacote não são
persistidos no servidor. O manifesto distingue o SHA-256 dos bytes enviados do
SHA-256 da representação normalizada em UTF-8/LF. Quando a fonte contém um
literal de credencial detectável, a emissão é bloqueada e a resposta contém
apenas o tipo e a linha do achado, nunca o valor.

## Pacote de evidências

O ZIP retornado em Base64 contém:

- fonte original normalizada e candidata;
- análises estáticas original e candidata;
- avaliação dos controles mínimos;
- comparação de preservação estática;
- limitações e plano de validação dinâmica futura;
- manifesto de maturidade `EXPERIMENTAL` no caminho canônico de versão;
- manifesto do pacote, checksums, changelog, instruções e rollback.

Ordem dos membros, timestamps, permissões, codificação e serialização JSON são
fixos. A mesma fonte, nome, versão e política produz os mesmos bytes e SHA-256.
Identificador de correlação e horário da requisição ficam fora do pacote canônico.

## Validação dinâmica futura

Para comprovar equivalência funcional, será necessário compilar e executar a
original e a candidata em ambiente Office isolado, com fixtures aprovadas,
dependências e efeitos colaterais controlados, comparação de saídas e evidência de
rollback. Essa etapa não faz parte desta entrega e não deve ser marcada como
concluída a partir do `PASS` estático.
