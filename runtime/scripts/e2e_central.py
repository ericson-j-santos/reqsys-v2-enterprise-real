"""E2E da Central Global contra a aplicação real (app.main via uvicorn).

Cobre caso positivo, controles negativos, idempotência e leitura por fonte
independente. Uso::

    QUEUE_BACKEND=memory STORAGE_BACKEND=memory \
        python -m uvicorn app.main:app --host 127.0.0.1 --port 8099 &
    CENTRAL_E2E_BASE_URL=http://127.0.0.1:8099 python scripts/e2e_central.py

Sai com código 1 se qualquer verificação falhar.
"""
import json, os, sys, urllib.error, urllib.request, uuid

BASE = os.environ.get("CENTRAL_E2E_BASE_URL", "http://127.0.0.1:8099").rstrip("/")
CID = f"e2e-{uuid.uuid4().hex[:12]}"
SHA_A = "a1b2c3d4" * 5
SHA_B = "f1e2d3c4" * 5
falhas = []

def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else None)

def check(nome, cond, detalhe=""):
    print(f"{'PASS' if cond else 'FAIL'}  {nome} {detalhe}")
    if not cond:
        falhas.append(nome)

def wr(titulo, rc, corr, **kw):
    return {"title": titulo, "project": "reqsys", "root_cause_id": rc,
            "correlation_id": corr, "signals": kw.pop("signals", []), **kw}

# --- PRÉ-CONDIÇÃO: instância limpa ------------------------------------------
# O limite de WIP é global; rodar contra uma Central já populada produziria
# reprovações que nada dizem sobre o código em teste.
st, existentes = call("GET", "/api/central/work-requests")
if st != 200:
    print(f"FAIL  precondicao_central_disponivel {st}")
    sys.exit(1)
if existentes:
    print(f"FAIL  precondicao_central_vazia: {len(existentes)} solicitações preexistentes; "
          "reinicie o runtime antes de executar o E2E")
    sys.exit(1)
print(f"PASS  precondicao_central_vazia  base={BASE}")

# --- POSITIVO: roteamento + ciclo até EVIDENCED -----------------------------
st, ci = call("POST", "/api/central/work-requests", wr("Reparar workflow de CI", "rc-ci-"+CID, CID, sha=SHA_A))
check("registro_201", st == 201, st)
check("roteou_ci_repair", ci and ci["executor"] == "ci_repair", ci and ci["routing_rule"])
rid = ci["request_id"]

st, prox = call("GET", "/api/central/next")
check("next_devolve_item_admitido", st == 200 and prox["request_id"] == rid, st)

st, _ = call("POST", f"/api/central/work-requests/{rid}/transition", {"status": "EXECUTING"})
check("transicao_executing", st == 200, st)

checks_ok = {"positive": "PASS", "negative_control": "PASS", "idempotency": "PASS", "independent_read": "PASS"}
st, ev = call("POST", "/api/central/evidence",
              {"request_id": rid, "sha": SHA_A, "environment": "dev", "checks": checks_ok})
check("evidencia_evidenced", st == 201 and ev["status"] == "EVIDENCED", ev and ev["status"])

st, fim = call("POST", f"/api/central/work-requests/{rid}/transition", {"status": "EVIDENCED"})
check("conclusao_aceita_com_evidencia", st == 200 and fim["status"] == "EVIDENCED", st)

# --- CONTROLE NEGATIVO 1: conclusão sem evidência completa ------------------
st, neg = call("POST", "/api/central/work-requests", wr("Ajustar stored procedure", "rc-sql-"+CID, CID+"x", signals=["SQL Server"], sha=SHA_A))
rid_neg = neg["request_id"]
check("roteou_sql", neg["executor"] == "sql", neg["routing_rule"])
call("GET", "/api/central/next")
call("POST", f"/api/central/work-requests/{rid_neg}/transition", {"status": "EXECUTING"})
call("POST", "/api/central/evidence", {"request_id": rid_neg, "sha": SHA_A, "environment": "dev",
                                       "checks": {"positive": "PASS"}})
st, corpo = call("POST", f"/api/central/work-requests/{rid_neg}/transition", {"status": "EVIDENCED"})
check("conclusao_recusada_sem_evidencia_completa", st == 409, st)

# --- CONTROLE NEGATIVO 2: evidência de SHA divergente é invalidada ----------
call("POST", "/api/central/evidence", {"request_id": rid_neg, "sha": SHA_A, "environment": "dev", "checks": checks_ok})
st, _ = call("POST", "/api/central/evidence", {"request_id": rid_neg, "sha": SHA_B, "environment": "dev",
                                               "checks": {"positive": "PASS"}})
st, corpo = call("POST", f"/api/central/work-requests/{rid_neg}/transition", {"status": "EVIDENCED"})
check("conclusao_recusada_apos_mudanca_de_sha", st == 409, st)

# --- CONTROLE NEGATIVO 3: bloqueio humano não entra na fila executável ------
st, hg = call("POST", "/api/central/work-requests", wr("Conceder admin consent no Graph", "rc-identity-"+CID, CID+"y", signals=["consentimento pendente"]))
check("human_gate_bloqueado", hg["executor"] == "human_gate" and hg["status"] == "BLOCKED", hg["routing_rule"])
st, prox = call("GET", "/api/central/next?executor=human_gate")
check("human_gate_fora_da_fila_executavel", st == 204, st)

# --- IDEMPOTÊNCIA: repetir o registro não duplica ---------------------------
st_a, antes = call("GET", "/api/central/work-requests")
st, dup = call("POST", "/api/central/work-requests", wr("Reparar workflow de CI", "rc-ci-"+CID, CID, sha=SHA_A))
st_b, depois = call("GET", "/api/central/work-requests")
check("registro_idempotente_mesmo_id", dup["request_id"] == rid, dup["request_id"])
check("registro_idempotente_sem_duplicata", len(antes) == len(depois), f"{len(antes)}->{len(depois)}")

# --- LEITURA INDEPENDENTE: ledger consultado por outro endpoint -------------
st, lido = call("GET", f"/api/central/evidence/{rid}")
check("leitura_independente_ledger", st == 200 and lido["status"] == "EVIDENCED" and lido["sha"] == SHA_A, st)

# --- WIP por causa raiz sob o limite default (3) ----------------------------
for n in range(4):
    call("POST", "/api/central/work-requests", wr(f"Sincronizar Planner com Teams {n}", f"rc-wip-{n}-{CID}", f"{CID}-w{n}"))
st, plano = call("GET", "/api/central/admission-plan")
check("wip_limita_causas_ativas", st == 200 and len(plano["admitted"]) <= plano["max_active_root_causes"],
      f"admitidas={len(plano['admitted'])} limite={plano['max_active_root_causes']} fila={len(plano['queued'])}")
check("wip_enfileira_excedente", len(plano["queued"]) > 0, len(plano["queued"]))

print("\nFALHAS:", falhas or "nenhuma")
sys.exit(1 if falhas else 0)
