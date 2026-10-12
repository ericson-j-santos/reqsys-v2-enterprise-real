import io
import json
import unittest
from urllib.error import HTTPError

from scripts.probe_pc24x7_dev_runtime_identity import ROUTES, ProbeError, run


class Response:
    status = 200

    def __init__(self, payload):
        self.raw = (
            payload
            if isinstance(payload, bytes)
            else json.dumps({"data": payload}).encode()
        )

    def read(self, n):
        return self.raw[:n]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class Opener:
    def __init__(self, values):
        self.values = values

    def open(self, req, timeout):
        value = self.values[req.full_url]
        if isinstance(value, Exception):
            raise value
        return Response(value)


def values(sha="a" * 40):
    base = "http://127.0.0.1:8210"
    common = {
        "service": "reqsys-api",
        "version": "1.2.3",
        "environment": "desenvolvimento",
    }
    return {
        base + ROUTES[0]: common,
        base + ROUTES[1]: {**common, "status": "ok", "check": "health"},
        base + ROUTES[2]: {**common, "status": "ready", "check": "readiness"},
        base + ROUTES[3]: {**common, "alive": True},
        base + ROUTES[4]: {**common, "build_sha": sha},
        base + ROUTES[5]: {
            **common,
            "dependencies": [
                {
                    "name": "database",
                    "status": "error",
                    "required": True,
                    "detail": "SECRET",
                }
            ],
        },
    }


class Tests(unittest.TestCase):
    def test_success_and_sanitization(self):
        out = run("a" * 40, Opener(values()))
        self.assertTrue(out["identity_validated"])
        self.assertTrue(out["routes"][ROUTES[4]]["runtime_sha_verified"])
        self.assertEqual("superficial", out["routes"][ROUTES[2]]["readiness_scope"])
        self.assertIs(out["routes"][ROUTES[3]]["alive"], True)
        self.assertNotIn("SECRET", json.dumps(out))

    def test_wrong_identity(self):
        v = values()
        v["http://127.0.0.1:8210" + ROUTES[0]]["environment"] = "prod"
        self.assertRaisesRegex(ProbeError, "identity", run, "a" * 40, Opener(v))

    def test_redirect(self):
        v = values()
        v["http://127.0.0.1:8210" + ROUTES[0]] = HTTPError(
            "x", 302, "redirect", {}, io.BytesIO()
        )
        self.assertRaisesRegex(ProbeError, "redirect", run, "a" * 40, Opener(v))

    def test_timeout(self):
        v = values()
        v["http://127.0.0.1:8210" + ROUTES[3]] = TimeoutError("secret detail")
        self.assertRaisesRegex(ProbeError, "transport_error", run, "a" * 40, Opener(v))

    def test_invalid_alive_type_is_preserved_as_sanitized_signal(self):
        for value in (1, "true", None, {"secret": "must-not-leak"}):
            v = values()
            v["http://127.0.0.1:8210" + ROUTES[3]]["alive"] = value
            out = run("a" * 40, Opener(v))
            live = out["routes"][ROUTES[3]]
            self.assertTrue(live["alive_invalid_type"])
            self.assertNotIn("must-not-leak", json.dumps(live))

    def test_invalid_status_type_is_preserved_as_sanitized_signal(self):
        for value in (1, True, None, ["bad"], {"secret": "must-not-leak"}):
            v = values()
            v["http://127.0.0.1:8210" + ROUTES[3]]["status"] = value
            out = run("a" * 40, Opener(v))
            live = out["routes"][ROUTES[3]]
            self.assertTrue(live["status_invalid_type"])
            self.assertNotIn("must-not-leak", json.dumps(live))

    def test_large_and_malformed(self):
        for raw, reason in (
            (b"x" * 262145, "too_large"),
            (b"not-json", "malformed_json"),
        ):
            v = values()
            v["http://127.0.0.1:8210" + ROUTES[0]] = raw
            with (
                self.subTest(reason=reason),
                self.assertRaisesRegex(ProbeError, reason),
            ):
                run("a" * 40, Opener(v))

    def test_sha_unknown_short_and_different(self):
        for observed in ("unknown", "abc", "b" * 40):
            out = run("a" * 40, Opener(values(observed)))
            self.assertFalse(out["routes"][ROUTES[4]]["runtime_sha_verified"])


if __name__ == "__main__":
    unittest.main()
