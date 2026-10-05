# PC24x7 — execução direta de tunnel e locator

## Objetivo
Eliminar o mesmo ImportError observado no runner Windows dos dois helpers chamados diretamente pelo workflow.

## Requisitos
1. `pc24x7_public_dev_tunnel.py` e `pc24x7_dev_locator_publisher.py` devem funcionar via `python scripts/<arquivo>.py`.
2. Quando `scripts.self_hosted_dev_maintenance` estiver disponível, reutilizar o módulo canônico.
3. Caso contrário, carregar o arquivo irmão por `importlib.util`.
4. Não alterar lógica de túnel, assinatura, DPAPI, probes ou publicação.
5. Testar ambos por subprocess com `--help`.

## Critérios de aceite
- Os dois subprocessos terminam com exit 0.
- CI completo passa no HEAD exato.
- Após merge, a reconciliação avança por tunnel e locator.
- Locator publicado continua exigindo os probes críticos Teams/Cofre.
