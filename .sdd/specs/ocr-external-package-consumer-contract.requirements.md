# Consumo governado do OCR Evidence Engine pelo ReqSys

## Requisito 1 — fornecedor imutável
O ReqSys deve consumir `ericson-j-santos/ocr-evidence-engine` por SHA completo validado. A branch móvel `main` não pode ser usada como identidade da dependência.

## Requisito 2 — autenticação temporária e mínima
O acesso ao repositório privado deve usar a GitHub App governada já utilizada pelo ReqSys, com token temporário limitado a `contents: read` e aos repositórios `reqsys-v2-enterprise-real` e `ocr-evidence-engine`. PAT pessoal de longa duração, credencial em URL e segredo persistido são proibidos.

## Requisito 3 — controle contra falso positivo por import local
Antes de instalar o pacote externo, o job deve retirar temporariamente `backend/ocr_evidencia` do caminho do consumidor e comprovar que `import ocr_evidencia` falha. Depois da instalação, deve comprovar por leitura independente de `__file__` que o import vem de `site-packages`, e não da cópia local nem do checkout do fornecedor.

## Requisito 4 — compatibilidade do consumidor
Com o pacote externo instalado, os contratos OCR do ReqSys devem executar no mesmo HEAD. O namespace público `ocr_evidencia` e a versão `1.2.0` devem permanecer compatíveis nesta etapa.

## Requisito 5 — falha fechada
Se a GitHub App não tiver acesso ao fornecedor privado, a emissão do token ou o checkout deve falhar e bloquear o contrato externo. Essa falha não pode ser convertida em sucesso, fallback para código local ou uso de credencial mais ampla.

## Requisito 6 — migração em duas etapas
Esta alteração somente valida o consumo externo. A cópia `backend/ocr_evidencia` não deve ser removida do repositório antes de o contrato externo e o E2E aplicável ficarem verdes no mesmo SHA. A remoção deve ocorrer em incremento posterior com rollback documentado.

## Critérios de aceite
1. O SHA do fornecedor é `15209941c4ddbf52da62cedc866510592b3172ee`.
2. O controle negativo sem a cópia local passa.
3. O token temporário consegue ler o fornecedor com somente `contents: read`.
4. O checkout confirma o SHA esperado.
5. O import instalado é comprovado em `site-packages`.
6. `backend/ocr_tests` fica verde usando o pacote externo.
7. Falha de acesso ao fornecedor permanece bloqueante e explicitamente evidenciada.
8. Nenhuma remoção definitiva da cópia local, deploy, promoção ou alteração de produção ocorre neste incremento.
