"""E2E de durabilidade da Central contra a aplicação real com backend Redis.

Prova que o plano de controle sobrevive ao processo. Executado em duas fases,
com um reinício do runtime entre elas::

    # fase 1 — cria a solicitação, conclui com evidência e imprime o id
    python scripts/e2e_central_durability.py seed
    # (reinicie o runtime aqui)
    # fase 2 — confirma que fila, estado e evidência continuam lá
    python scripts/e2e_central_durability.py verify WR-XXXX

O id também é gravado em ``CENTRAL_E2E_STATE_FILE`` (default
``.tmp/central-e2e-durability.json``), então ``verify`` pode ser chamado sem
argumento. Sai com código 1 se qualquer verificação falhar.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("CENTRAL_E2E_BASE_URL", "http://127.0.0.1:8099").rstrip("/")
STATE_FILE = pathlib.Path(
    os.environ.get("CENTRAL_E2E_STATE_FILE", ".tmp/central-e2e-durability.json")
)
SHA = "d" * 40
TODOS_PASS = {
    "positive": "PASS",
    "negative_control": "PASS",
    "idempotency": "PASS",
    "independent_read": "PASS",
}

falhas: list[str] = []


def call(method: str, path: str, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data) as resposta:
            raw = resposta.read()
            return resposta.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw else None)


def check(nome: str, condicao: bool, detalhe="") -> None:
    print(f"{'PASS' if condicao else 'FAIL'}  {nome} {detalhe}")
    if not condicao:
        falhas.append(nome)


def seed() -> str:
    correlation_id = f"e2e-dur-{uuid.uuid4().hex[:12]}"
    st, criada = call(
        "POST",
        "/api/central/work-requests",
        {
            "title": "Reparar workflow de CI (durabilidade)",
            "project": "reqsys",
            "root_cause_id": f"rc-dur-{correlation_id}",
            "correlation_id": correlation_id,
            "signals": ["pipeline vermelho"],
            "sha": SHA,
        },
    )
    check("seed_registro_201", st == 201, st)
    if st != 201:
        sys.exit(1)

    request_id = criada["request_id"]
    call("GET", "/api/central/next")
    st, _ = call(
        "POST", f"/api/central/work-requests/{request_id}/transition", {"status": "EXECUTING"}
    )
    check("seed_transicao_executing", st == 200, st)

    st, evidencia = call(
        "POST",
        "/api/central/evidence",
        {"request_id": request_id, "sha": SHA, "environment": "dev", "checks": TODOS_PASS},
    )
    check("seed_evidencia_evidenced", st == 201 and evidencia["status"] == "EVIDENCED", st)

    st, final = call(
        "POST", f"/api/central/work-requests/{request_id}/transition", {"status": "EVIDENCED"}
    )
    check("seed_conclusao", st == 200 and final["status"] == "EVIDENCED", st)

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"request_id": request_id, "sha": SHA}), encoding="utf-8")
    print(f"\nrequest_id={request_id}  (gravado em {STATE_FILE})")
    return request_id


def verify(request_id: str | None) -> None:
    if request_id is None:
        if not STATE_FILE.exists():
            print(f"FAIL  verify_sem_estado: informe o request_id ou rode 'seed' antes ({STATE_FILE})")
            sys.exit(1)
        request_id = json.loads(STATE_FILE.read_text(encoding="utf-8"))["request_id"]

    st, solicitacao = call("GET", f"/api/central/work-requests/{request_id}")
    check("solicitacao_sobreviveu_ao_reinicio", st == 200, st)
    if st != 200:
        print("\nFALHAS:", falhas)
        sys.exit(1)

    check("status_preservado", solicitacao["status"] == "EVIDENCED", solicitacao["status"])
    check("sha_preservado", solicitacao["sha"] == SHA, solicitacao["sha"])
    check(
        "roteamento_preservado",
        solicitacao["executor"] == "ci_repair" and solicitacao["routing_rule"] == "ci.repair",
        solicitacao["routing_rule"],
    )

    st, evidencia = call("GET", f"/api/central/evidence/{request_id}")
    check("evidencia_sobreviveu_ao_reinicio", st == 200, st)
    if st == 200:
        check("evidencia_ainda_evidenced", evidencia["status"] == "EVIDENCED", evidencia["status"])
        check("evidencia_no_mesmo_sha", evidencia["sha"] == SHA, evidencia["sha"])

    st, lista = call("GET", "/api/central/work-requests")
    check(
        "fila_reconstruida_do_estado_duravel",
        st == 200 and any(item["request_id"] == request_id for item in lista),
        f"itens={len(lista) if isinstance(lista, list) else 'n/a'}",
    )


def main() -> int:
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo == "seed":
        seed()
    elif modo == "verify":
        verify(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        print(__doc__)
        return 2
    print("\nFALHAS:", falhas or "nenhuma")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
