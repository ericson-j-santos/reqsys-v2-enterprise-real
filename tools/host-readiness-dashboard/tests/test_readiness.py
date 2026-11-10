"""Testes de API HTTP real e contrato de recibos; nenhum host é acionado."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.readiness import GATES, canonical, handler_factory, ingest, snapshots, verify_receipt

KEY = "v" * 40
RULES = "86abe65b22781c2f608a7d7286ce3a28cd48aaaf"
SHA = "a" * 40
DIGEST = "b" * 64


def signed_receipt(**overrides):
    obj = {
        "schema_version": "1", "event_id": "test-event-12345", "host_id": "desktop", "physical_id": "DESKTOP-PDQK954",
        "observed_at": datetime.now(timezone.utc).isoformat(), "source": "github_api_and_gateway_receipt",
        "source_sha": SHA, "rules_sha": RULES, "profile": "NORMAL",
        "runner": {"name": "DESKTOP-PDQK954-runtime", "version": "2.338.0", "labels": ["self-hosted", "pc24x7"]},
        "gates": {k: True for k in GATES}, "cost_guard": "COST_ZERO_CONFIRMED",
        "cost_evidence": "run/test local: orçamento de teste simulado, não é evidência real",
        "independent_readback": {"verified": True, "artifact_sha256": DIGEST, "readback_sha256": DIGEST},
        "block": "continuidade", "next_action": "Avaliar handoff físico sem dispatch", "requires_human": False,
        "pickup_individual": True,
    }
    obj.update(overrides)
    obj["signature"] = hmac.new(KEY.encode(), canonical(obj).encode(), hashlib.sha256).hexdigest()
    return obj


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "evidence.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_accept_and_readback_replay(self):
        receipt = signed_receipt()
        first = ingest(self.db, receipt, KEY, RULES)
        self.assertFalse(first["replayed"])
        self.assertTrue(first["storage_readback_verified"])
        second = ingest(self.db, receipt, KEY, RULES)
        self.assertTrue(second["replayed"])
        hosts, history = snapshots(self.db, KEY, RULES)
        self.assertTrue(hosts[0]["ready_for_work"])
        self.assertEqual(len(history), 1)

    def test_signature_and_identity_rejected(self):
        receipt = signed_receipt()
        receipt["gates"]["gateway"] = False
        with self.assertRaisesRegex(ValueError, "invalid_signature"):
            ingest(self.db, receipt, KEY, RULES)
        for kwargs in ({"physical_id": "DESKTOP-RP23OGS"}, {"rules_sha": SHA}, {"profile": "ESTUDO"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                verify_receipt(signed_receipt(**kwargs), KEY, RULES)

    def test_expiration_and_clock_skew(self):
        for delta in (-310, +60):
            old = (datetime.now(timezone.utc) + timedelta(seconds=delta)).isoformat()
            with self.subTest(delta=delta), self.assertRaisesRegex(ValueError, "observation_expired_or_future"):
                ingest(self.db, signed_receipt(observed_at=old), KEY, RULES)

    def test_false_gate_fails_closed_and_stale_afterwards(self):
        receipt = signed_receipt(gates={**{k: True for k in GATES}, "lease": False})
        ingest(self.db, receipt, KEY, RULES)
        now = datetime.now(timezone.utc)
        hosts, _ = snapshots(self.db, KEY, RULES, now=now)
        self.assertFalse(hosts[0]["ready_for_work"])
        hosts, _ = snapshots(self.db, KEY, RULES, now=now + timedelta(minutes=8))
        self.assertFalse(hosts[0]["ready_for_work"])

    def test_stored_signature_also_checked_on_read(self):
        ingest(self.db, signed_receipt(), KEY, RULES)
        import sqlite3
        with sqlite3.connect(self.db) as db:
            row = db.execute("SELECT payload FROM evidence").fetchone()[0]
            obj = json.loads(row)
            obj["gates"]["identity"] = True
            obj["next_action"] = "Forjar estado"
            altered = canonical(obj)
            db.execute("UPDATE evidence SET payload=?, digest=?", (altered, hashlib.sha256(altered.encode()).hexdigest()))
        hosts, history = snapshots(self.db, KEY, RULES)
        self.assertEqual(history, [])
        self.assertFalse(hosts[0]["ready_for_work"])

    def test_missing_db_always_blocked(self):
        hosts, hist = snapshots(self.db, KEY, RULES)
        self.assertEqual(hist, [])
        self.assertEqual(len(hosts), 3)
        self.assertTrue(all(h["ready_for_work"] is False for h in hosts))
        self.assertTrue(all(h["reason"] == "NO_EXTERNAL_EVIDENCE" for h in hosts))
        self.assertFalse(self.db.exists())

    def test_conflicting_event_rejected(self):
        ingest(self.db, signed_receipt(), KEY, RULES)
        with self.assertRaisesRegex(ValueError, "event_id_conflict"):
            ingest(self.db, signed_receipt(next_action="Outro evento no mesmo ID"), KEY, RULES)

    def test_http_auth_read_only_and_no_continuity_claim(self):
        html = Path(self.tmp.name) / "index.html"
        html.write_text("<h1>DEV</h1>")
        srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(self.db, "token-" + "x" * 24, html, KEY, RULES))
        task = threading.Thread(target=srv.serve_forever, daemon=True)
        task.start()
        url = f"http://127.0.0.1:{srv.server_port}/api/v1/readiness"
        try:
            with self.assertRaises(HTTPError) as ctx:
                urlopen(url, timeout=3)
            self.assertEqual(ctx.exception.code, 401)
            with self.assertRaises(HTTPError) as ctx:
                urlopen(Request(url, method="POST", headers={"Authorization": "Basic " + base64.b64encode(b"x:token-" + b"x" * 24).decode()}), timeout=3)
            self.assertEqual(ctx.exception.code, 405)
            auth = base64.b64encode(("user:token-" + "x" * 24).encode()).decode()
            with urlopen(Request(url, headers={"Authorization": "Basic " + auth}), timeout=3) as resp:
                data = json.load(resp)
            self.assertFalse(data["continuity_certified"])
            self.assertIsNone(data["selected_host"])
            self.assertTrue(all(h["ready_for_work"] is False for h in data["hosts"]))
        finally:
            srv.shutdown()
            srv.server_close()
            task.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
