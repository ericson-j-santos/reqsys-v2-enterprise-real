# Analisador de Legado VBA — incremento 1

## Objetivo

Permitir que o ReqSys receba código VBA legado e produza uma análise técnica rastreável sem executar a macro.

## Superfície de API

O roteador é anexado à API canônica de requisitos:

- `GET /api/requisitos/legado/vba/readiness`
- `POST /api/requisitos/legado/vba/analisar`

Ambos exigem identidade administrativa do ReqSys.

## Entradas suportadas

- `.bas`
- `.cls`
- `.frm`
- `.vba`
- `.txt`

O limite padrão é 2 MiB e pode ser alterado por ambiente com `VBA_ANALYZER_MAX_UPLOAD_BYTES`.

Contêineres binários Office (`.xlsm`, `.xlsb`, `.xlam`, `.docm`, `.dotm`) são bloqueados neste incremento. O ReqSys não tenta executar o Office nem interpretar `vbaProject.bin` implicitamente.

## Saídas

A análise retorna:

1. inventário do módulo e procedimentos;
2. fluxo de chamadas entre procedimentos conhecidos;
3. dependências de planilhas, arquivos, COM, ADODB e SQL;
4. regras condicionais encontradas;
5. candidatos a requisito com linha, módulo, procedimento e confiança;
6. riscos técnicos, incluindo segredo embutido, `On Error Resume Next`, `Shell`, `SendKeys`, chamadas nativas e caminhos fixos;
7. plano de modernização priorizado.

Candidatos de requisito sempre retornam `requires_human_validation=true`. O incremento não cria requisitos automaticamente.

## Segurança

- análise exclusivamente estática (`analysis_type=static_only`);
- `execution_performed=false` em todas as respostas;
- conteúdo de origem não é persistido pela API (`source_persisted=false`);
- SHA-256 calculado sobre a fonte normalizada para evidência/idempotência;
- senhas detectadas em linhas de conexão são mascaradas na evidência;
- nome de arquivo é reduzido ao nome base, sem uso como caminho local;
- conteúdo com byte NUL é rejeitado como binário.

## Próximo incremento

Extrair módulos VBA de contêineres Office de forma governada, a partir de `vbaProject.bin`, sem executar Excel/Word. A execução dinâmica, se vier a existir, deve ocorrer apenas em Windows isolado e descartável, com rede, credenciais e escrita externa bloqueadas por padrão.
