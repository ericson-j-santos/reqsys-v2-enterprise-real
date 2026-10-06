# Pacote OCR externo no build/runtime do ReqSys

## Requisito 1 — lock único e imutável
O fornecedor deve ser identificado em `config/ocr-engine-lock.json` pelo repositório privado exato, SHA completo de 40 caracteres e versão pública esperada. Branch móvel não pode identificar o artefato de runtime.

## Requisito 2 — credencial efêmera fora do Docker
A aquisição do código privado deve ocorrer no executor do GitHub Actions usando a GitHub App governada, token temporário com somente `contents: read` e escopo apenas para `reqsys-v2-enterprise-real` e `ocr-evidence-engine`. Token, chave privada e URL autenticada não podem entrar no contexto Docker, wheel, proveniência ou imagem.

## Requisito 3 — artefato verificável
O checkout deve ser verificado contra o SHA do lock. O wheel deve ser construído com `--no-deps` e validado pelo contrato de distribuição do próprio fornecedor. O bundle fechado deve conter exatamente um wheel, `provenance.json` no schema `1.1.0`, `MANIFEST.sha256` e `SHA256SUMS`; os dois manifestos devem ser byte a byte idênticos e registrar o SHA-256 do wheel. Nome, versão, repositório e SHA-fonte devem ser compatíveis com o lock.

## Requisito 4 — build fail-closed
Quando `OCR_EXTERNAL_PACKAGE_REQUIRED=1`, o Dockerfile deve exigir o bundle fechado, os dois manifestos idênticos, exatamente um wheel e proveniência com repositório, SHA, versão, tamanho e SHA-256 coerentes. Ausência, entrada adicional ou divergência deve falhar antes da instalação; não pode existir fallback silencioso para a cópia local.

## Requisito 5 — runtime realmente externo
No modo externo obrigatório, o wheel deve ser instalado e `/app/ocr_evidencia` deve ser removido antes da prova de import. O import final deve resolver em `site-packages` e apresentar a versão `1.2.0`. Wheel/proveniência temporários devem ser removidos da imagem após instalação.

## Requisito 6 — fonte local preservada nesta etapa
`backend/ocr_evidencia` permanece versionado no repositório para rollback e desenvolvimento local. Sua remoção física só pode ocorrer depois de o build de imagem externo e o E2E aplicável ficarem verdes no mesmo SHA.

## Requisito 7 — caminhos canônicos
`fly-dev-fast-deploy.yml` e `fly-enterprise-sync.yml` devem preparar o pacote externo antes do deploy da API e passar `OCR_EXTERNAL_PACKAGE_REQUIRED=1`, SHA e versão ao build. O `OCR Benchmark Gate` deve usar o mesmo SHA declarado no lock, e o contrato automatizado deve bloquear divergência entre essas duas fontes. Assim, qualquer deploy futuro desses caminhos falha fechado se o pacote privado não puder ser preparado.

## Requisito 8 — validação sem deploy
A PR deve construir a imagem real com o modo externo obrigatório e executar um processo independente dentro dela que confirme origem em `site-packages`, versão e ausência de `/app/ocr_evidencia`. Antes disso, um controle negativo deve comprovar que o build obrigatório sem wheel falha.

## Requisito 9 — fronteira operacional
Este incremento não autoriza deploy, promoção, produção, rotação de segredo nem alteração administrativa. O rollback operacional é o SHA anterior do ReqSys; o rollback da dependência é feito por alteração explícita do lock para outro SHA já validado.

## Critérios de aceite
1. Lock e OCR Benchmark Gate apontam para `15dd067032d7c55e22186ef3587c0d694d0392fd`, versão `1.2.0`, sem divergência entre as duas fontes.
2. Token temporário mantém `contents: read` e escopo mínimo.
3. O verificador do fornecedor aprova o bundle; `MANIFEST.sha256` e `SHA256SUMS` são idênticos e correspondem ao wheel.
4. Controle negativo sem wheel falha.
5. Build positivo com wheel externo passa.
6. Container comprova import em `site-packages` e ausência da cópia local em runtime.
7. Workflows canônicos exigem pacote externo nos futuros deploys.
8. CI/SDD/gates ficam verdes no HEAD atual.
9. Nenhum deploy ou produção é executado por esta PR.
