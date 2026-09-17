"""E2E do ciclo executável da Central contra a aplicação real.

Sobe um executor HTTP de verdade (servidor local que cumpre o contrato do
`HttpExecutorAdapter`), registra uma solicitação na Central, dispara um ciclo do
worker e confirma que o efeito foi produzido e que a solicitação só chega a
`EVIDENCED` quando as quatro verificações passam.

Uso::

    # 1. suba o runtime apontando para o executor deste script
    CENTRAL_EXECUTOR_ENDPOINTS='{"ci_repair": {"url": "http://127.0.0.1:8098/executar",
                                               "negative_probe": {"sha": "invalido"}},
                                 "graph": "http://127.0.0.1:8098/executar"}' \
      python -m uvicorn app.main:app --host 127.0.0.1 --port 8099 &
    # 2. rode o E2E (ele sobe o executor na 8098)
    python scripts/e2e_central_executor.py

Sai com código 1 se qualquer verificação falhar.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

BASE = os.environ.get("CENTRAL_E2E_BASE_URL", "http://127.0.0.1:8099").rstrip("/")
EXECUTOR_PORT = int(os.environ.get("CENTRAL_E2E_EXECUTOR_PORT", "8098"))
SHA = "e" * 40

falhas: list[str] = []
#: Efeitos realmente produzidos pelo executor: idempotency_key -> effect_id.
EFEITOS: dict[str, str] = {}
POSTS: list[dict] = []


class ExecutorHandler(BaseHTTPRequestHandler):
    """Executor de referência: cumpre o contrato e é auditável por leitura."""

    def log_message(self, *_args) -> None:  # silencia o log do http.server
        return

    def _responder(self, status: int, corpo: dict) -> None:
        dados = json.dumps(corpo).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self) -> None:  # noqa: N802 - assinatura do http.server
        partes = urlparse(self.path)
        if partes.path == "/verificar":
            effect_id = parse_qs(partes.query).get("effect_id", [""])[0]
            # Leitura independente: confirma pelo registro do executor.
            confirmado = effect_id in EFEITOS.values()
            self._responder(200, {"effect_id": effect_id, "confirmed": confirmado})
            return
        if partes.path == "/efeitos":
            self._responder(200, {"efeitos": EFEITOS, "posts": len(POSTS)})
            return
        self._responder(404, {"erro": "rota desconhecida"})

    def do_POST(self) -> None:  # noqa: N802 - assinatura do http.server
        tamanho = int(self.headers.get("Content-Length", "0"))
        corpo = json.loads(self.rfile.read(tamanho) or b"{}")
        POSTS.append(corpo)

        chave = corpo.get("idempotency_key")
        if not chave or not corpo.get("request_id"):
            # Controle negativo: carga inválida precisa ser recusada.
            self._responder(400, {"accepted": False, "erro": "payload invalido"})
            return

        duplicado = chave in EFEITOS
        if not duplicado:
            EFEITOS[chave] = f"efeito-{len(EFEITOS) + 1}"
        effect_id = EFEITOS[chave]
        self._responder(
            200,
            {
                "accepted": True,
                "effect_id": effect_id,
                "duplicate_effect": duplicado,
                "verification_url": (
                    f"http://127.0.0.1:{EXECUTOR_PORT}/verificar?effect_id={effect_id}"
                ),
                "evidence_run_url": f"http://127.0.0.1:{EXECUTOR_PORT}/efeitos",
            },
        )


def call(method: str, url: str, body=None):
    req = urllib.request.Request(url, method=method)
    dados = None
    if body is not None:
        dados = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, dados) as resposta:
            return resposta.status, _corpo(resposta.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _corpo(exc.read())


def _corpo(raw: bytes):
    """Erro do servidor pode não ser JSON; reportar isso é melhor que estourar."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"corpo_nao_json": raw[:200].decode("utf-8", "replace")}


def central(method: str, path: str, body=None):
    return call(method, BASE + path, body)


def check(nome: str, condicao: bool, detalhe="") -> None:
    print(f"{'PASS' if condicao else 'FAIL'}  {nome} {detalhe}")
    if not condicao:
        falhas.append(nome)


def registrar(titulo: str, sinais: list[str], sha: str | None = SHA):
    cid = f"e2e-exec-{uuid.uuid4().hex[:12]}"
    corpo = {
        "title": titulo,
        "project": "reqsys",
        "root_cause_id": f"rc-{cid}",
        "correlation_id": cid,
        "signals": sinais,
    }
    if sha:
        corpo["sha"] = sha
    return central("POST", "/api/central/work-requests", corpo)


def main() -> int:
    servidor = HTTPServer(("127.0.0.1", EXECUTOR_PORT), ExecutorHandler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    print(f"PASS  executor_local_no_ar  porta={EXECUTOR_PORT}")

    try:
        st, existentes = central("GET", "/api/central/work-requests")
        if st != 200:
            print(f"FAIL  precondicao_central_disponivel {st}")
            return 1
        if existentes:
            print(
                f"FAIL  precondicao_central_vazia: {len(existentes)} solicitações preexistentes; "
                "reinicie o runtime antes do E2E"
            )
            return 1
        print("PASS  precondicao_central_vazia")

        # --- POSITIVO: ciclo completo até EVIDENCED ------------------------
        st, criada = registrar("Reparar workflow de CI", ["pipeline vermelho"])
        check("registro_201", st == 201, st)
        check("roteou_ci_repair", criada and criada["executor"] == "ci_repair", criada["routing_rule"])
        rid = criada["request_id"]

        st, ciclo = central("POST", "/api/central/worker/cycle")
        check("ciclo_200", st == 200, st)
        check("ciclo_evidenciou", ciclo and ciclo["resultado"] == "EVIDENCIADO", ciclo)
        check("ciclo_reporta_item", ciclo and ciclo["request_id"] == rid, ciclo and ciclo["request_id"])

        st, final = central("GET", f"/api/central/work-requests/{rid}")
        check("solicitacao_evidenciada", final["status"] == "EVIDENCED", final["status"])

        st, evidencia = central("GET", f"/api/central/evidence/{rid}")
        check("evidencia_completa", evidencia["status"] == "EVIDENCED", evidencia["status"])
        check("evidencia_no_sha_corrente", evidencia["sha"] == SHA, evidencia["sha"])
        check(
            "quatro_verificacoes_pass",
            all(valor == "PASS" for valor in evidencia["checks"].values()),
            evidencia["checks"],
        )

        # --- EFEITO REAL: leitura independente no próprio executor ---------
        st, efeitos = call("GET", f"http://127.0.0.1:{EXECUTOR_PORT}/efeitos")
        check("executor_produziu_efeito", st == 200 and len(efeitos["efeitos"]) == 1, efeitos["efeitos"])
        check(
            "idempotencia_um_efeito_para_varios_posts",
            efeitos["posts"] >= 3 and len(efeitos["efeitos"]) == 1,
            f"posts={efeitos['posts']} efeitos={len(efeitos['efeitos'])}",
        )

        # --- CONTROLE NEGATIVO 1: sem controle negativo não conclui --------
        # 'graph' foi configurado sem negative_probe: a evidência fica parcial.
        st, parcial = registrar("Sincronizar Planner com Teams", ["graph"])
        check("roteou_graph", parcial["executor"] == "graph", parcial["routing_rule"])
        st, ciclo = central("POST", "/api/central/worker/cycle?executor=graph")
        check("ciclo_sem_probe_nao_conclui", ciclo["resultado"] == "AGUARDANDO_EVIDENCIA", ciclo)
        check(
            "pendente_e_o_controle_negativo",
            ciclo["verificacoes_pendentes"] == ["negative_control"],
            ciclo["verificacoes_pendentes"],
        )
        st, estado = central("GET", f"/api/central/work-requests/{parcial['request_id']}")
        check("permanece_aguardando_evidencia", estado["status"] == "AWAITING_EVIDENCE", estado["status"])

        # --- CONTROLE NEGATIVO 2: executor não configurado bloqueia --------
        st, sem_exec = registrar("Ajustar stored procedure", ["SQL Server"])
        check("roteou_sql", sem_exec["executor"] == "sql", sem_exec["routing_rule"])
        st, ciclo = central("POST", "/api/central/worker/cycle?executor=sql")
        check("ciclo_bloqueia_sem_executor", ciclo["resultado"] == "BLOQUEADO", ciclo)
        check(
            "bloqueio_nomeia_o_que_falta",
            ciclo["blocker"] == "executor_nao_configurado:sql",
            ciclo["blocker"],
        )
        st, estado = central("GET", f"/api/central/work-requests/{sem_exec['request_id']}")
        check("bloqueio_tem_proxima_acao", bool(estado["next_action"]), estado["next_action"])

        # --- CONTROLE NEGATIVO 3: human_gate nunca é executado -------------
        st, humano = registrar("Conceder admin consent no Graph", ["consentimento pendente"])
        check("human_gate_bloqueado", humano["executor"] == "human_gate", humano["routing_rule"])
        st, ciclo = central("POST", "/api/central/worker/cycle?executor=human_gate")
        check("human_gate_nao_executa", ciclo["resultado"] == "OCIOSO", ciclo)

        # --- IDEMPOTÊNCIA DO CICLO: reexecutar não refaz o concluído -------
        # O estado é lido agora, não reaproveitado de leituras anteriores:
        # comparar com um total antigo mediria os ciclos do meio, não este.
        st, antes = call("GET", f"http://127.0.0.1:{EXECUTOR_PORT}/efeitos")
        st, ciclo = central("POST", "/api/central/worker/cycle?executor=ci_repair")
        check("ciclo_ocioso_apos_concluir", ciclo["resultado"] == "OCIOSO", ciclo["resultado"])
        st, depois = call("GET", f"http://127.0.0.1:{EXECUTOR_PORT}/efeitos")
        check(
            "ciclo_nao_reexecuta_concluido",
            depois["posts"] == antes["posts"] and depois["efeitos"] == antes["efeitos"],
            f"posts={depois['posts']} (antes {antes['posts']})",
        )
    finally:
        servidor.shutdown()

    print("\nFALHAS:", falhas or "nenhuma")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
