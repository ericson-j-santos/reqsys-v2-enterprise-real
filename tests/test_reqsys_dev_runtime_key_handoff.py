"""Key continuity contracts. Fixtures contain fake keys, never runtime values."""
import base64
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

handoff = load("runtime_key_handoff", ROOT / "scripts/reqsys_dev_runtime_key_handoff.py")
loader = load("runtime_secret_loader", ROOT / "infra/self-hosted/start_api.py")
SHA = "a" * 40
CID = "c" * 64


class Private:
    def directory(self, path):
        path.mkdir(parents=True, exist_ok=True)

    def check(self, path):
        if not path.exists():
            raise FileNotFoundError(path)

    def create(self, path, content):
        with path.open("xb") as output:
            output.write(content)

    def preserving(self, path, content):
        if path.exists():
            if path.read_bytes() != content:
                raise handoff.HandoffError("existing_configuration_mismatch")
            return
        self.create(path, content)


def source():
    return {
        "jwt_secret": " original nonhex legacy jwt key \r\n ",
        "cofre_keyring_passphrase": "original cofre passphrase\r",
        "vault_service_name": "existing-vault-service",
        "ai_conversation_content_encryption_key_b64": base64.b64encode(b"a" * 32).decode(),
        "ai_encrypted_count": 1, "ai_mode": "enforce",
        "keyring_cipher_b64": base64.b64encode(b"fakeencryptedkeyring" * 3).decode(),
        "jwt_resolution": "env", "ai_resolution": "vault",
        "source_database": "reqsys", "source_role": "reqsys_app",
        "source_postgres_version": "160015", "jwt_issuer": "existing-api",
        "jwt_audience": "existing-ui",
    }


class KeyHandoffTests(unittest.TestCase):
    def patches(self, value):
        return (
            patch.object(handoff, "inspect_source", return_value=CID),
            patch.object(handoff, "capture", return_value=json.dumps(value).encode()),
            patch.object(handoff, "protect", side_effect=lambda raw: b"fake-dpapi:" + raw),
            patch.object(handoff, "unprotect", side_effect=lambda raw: raw[len(b"fake-dpapi:"):]),
        )

    def preserve(self, root, value):
        inspect, capture, protect, unprotect = self.patches(value)
        with inspect, capture, protect, unprotect:
            return handoff.preserve(root, SHA, Private())

    def test_exact_handoff_idempotent_and_metadata_excludes_key_material(self):
        value = source()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.patches(value)[3]:
                first = self.preserve(root, value)
                saved = handoff.snapshot_path(root).read_bytes()
                self.preserve(root, value)
                self.assertEqual(handoff.snapshot_path(root).read_bytes(), saved)
                proof = handoff.validate_existing(root, SHA, Private(), CID)
            self.assertEqual(first, proof)
            self.assertEqual((root / "secrets/jwt_secret").read_bytes(),
                             value["jwt_secret"].encode())
            self.assertEqual((root / "cofre-data/cofre-keyring.enc").read_bytes(),
                             base64.b64decode(value["keyring_cipher_b64"]))
            public = json.dumps(proof)
            for field in handoff.SECRET_FIELDS:
                self.assertNotIn(value[field], public)
            self.assertNotIn("keyring_cipher_b64", public)
            self.assertEqual(proof["jwt_issuer"], "existing-api")
            self.assertEqual(proof["jwt_audience"], "existing-ui")
            self.assertFalse(proof["source_written"])

    def test_edited_original_key_or_keyring_blocks_fidelity(self):
        for path in ("secrets/jwt_secret", "cofre-data/cofre-keyring.enc"):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.preserve(root, source())
                (root / path).write_bytes(b"changed")
                with self.patches(source())[3]:
                    with self.assertRaises(handoff.HandoffError):
                        handoff.validate_existing(root, SHA, Private(), CID)

    def test_source_identity_or_target_sha_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.preserve(root, source())
            with self.patches(source())[3]:
                for target, container in ((SHA, "d" * 64), ("b" * 40, CID)):
                    with self.assertRaises(handoff.HandoffError):
                        handoff.validate_existing(root, target, Private(), container)

    def test_changed_source_never_overwrites_existing_snapshot_or_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = source()
            self.preserve(root, value)
            snapshot = handoff.snapshot_path(root).read_bytes()
            other = copy.deepcopy(value)
            other["jwt_secret"] = "different-original"
            with self.assertRaisesRegex(handoff.HandoffError, "existing_key_snapshot_conflict"):
                self.preserve(root, other)
            self.assertEqual(handoff.snapshot_path(root).read_bytes(), snapshot)
            self.assertEqual((root / "secrets/jwt_secret").read_bytes(),
                             value["jwt_secret"].encode())

    def test_missing_original_or_required_ai_key_fails_before_snapshot(self):
        for name in ("jwt_secret", "cofre_keyring_passphrase",
                     "ai_conversation_content_encryption_key_b64", "keyring_cipher_b64"):
            value = source()
            value[name] = ""
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with self.assertRaises(handoff.HandoffError):
                    self.preserve(root, value)
                self.assertFalse(handoff.snapshot_path(root).exists())

    def test_no_ai_ciphertext_and_disabled_mode_allow_absent_ai_key(self):
        value = source()
        value.update(ai_conversation_content_encryption_key_b64="",
                     ai_encrypted_count=0, ai_mode="off", ai_resolution="absent")
        with tempfile.TemporaryDirectory() as temporary:
            proof = self.preserve(Path(temporary), value)
            self.assertFalse(proof["ai_key_preserved"])

    def test_source_probe_contains_only_fixed_read_only_targets(self):
        code = handoff.SOURCE_COLLECTOR
        self.assertIn('read_secret_from_remote_vault = lambda _key: None', code)
        self.assertIn('SET TRANSACTION READ ONLY', code)
        self.assertNotIn("write_secret", code)
        self.assertNotIn("init_vault", code)
        self.assertNotIn("keyring.set_password", code)
        self.assertIn('"/run/secrets/cofre_keyring_passphrase"', code)
        self.assertIn('"/data/cofre-keyring.enc"', code)

    def test_loader_preserves_spaces_cr_and_newlines_exactly(self):
        value = source()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "db_app_password").write_text("e" * 64 + "\n")
            for name in handoff.SECRET_FIELDS:
                (root / name).write_bytes(value[name].encode())
            output = io.StringIO()
            with patch.dict(os.environ, {"REQSYS_REQUIRE_RUNTIME_KEY_HANDOFF": "1"}, clear=True), \
                    patch("sys.stdout", output):
                loader.configure(root)
                self.assertEqual(os.environ["JWT_SECRET"], value["jwt_secret"])
                self.assertEqual(os.environ["COFRE_KEYRING_PASSPHRASE"],
                                 value["cofre_keyring_passphrase"])
                self.assertEqual(os.environ["AI_CONVERSATION_CONTENT_ENCRYPTION_KEY_B64"],
                                 value["ai_conversation_content_encryption_key_b64"])
            self.assertEqual(output.getvalue(), "")

    def test_fresh_portable_three_files_retains_original_hex_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, value in (
                ("db_owner_password", "d" * 64), ("db_app_password", "e" * 64),
                ("jwt_secret", "f" * 64),
            ):
                (root / name).write_text(" " + value + "\r\n")
            before = sorted(path.name for path in root.iterdir())
            with patch.dict(os.environ, {}, clear=True):
                loader.configure(root)
                self.assertEqual(os.environ["JWT_SECRET"], "f" * 64)
                self.assertNotIn("COFRE_KEYRING_PASSPHRASE", os.environ)
                self.assertNotIn("AI_CONVERSATION_CONTENT_ENCRYPTION_KEY_B64", os.environ)
            self.assertEqual(sorted(path.name for path in root.iterdir()), before)

    def test_migration_missing_passphrase_or_ai_file_blocks_before_env_changes(self):
        for missing in ("cofre_keyring_passphrase",
                        "ai_conversation_content_encryption_key_b64"):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "db_app_password").write_text("e" * 64)
                for name, value in source().items():
                    if name in handoff.SECRET_FIELDS and name != missing:
                        (root / name).write_bytes(value.encode())
                with patch.dict(os.environ, {"REQSYS_REQUIRE_RUNTIME_KEY_HANDOFF": "1"}, clear=True):
                    with self.assertRaises(FileNotFoundError):
                        loader.configure(root)
                    self.assertNotIn("JWT_SECRET", os.environ)
                    self.assertNotIn("DATABASE_URL", os.environ)

    def test_fresh_optional_cofre_files_only_loaded_when_present(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "db_app_password").write_text("e" * 64)
            (root / "jwt_secret").write_text("f" * 64)
            (root / "cofre_keyring_passphrase").write_bytes(b" exact optional passphrase\r")
            with patch.dict(os.environ, {}, clear=True):
                loader.configure(root)
                self.assertEqual(os.environ["COFRE_KEYRING_PASSPHRASE"],
                                 " exact optional passphrase\r")
                self.assertNotIn("AI_CONVERSATION_CONTENT_ENCRYPTION_KEY_B64", os.environ)

    def test_fresh_stack_does_not_accept_legacy_nonhex_jwt_without_migration_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "db_app_password").write_text("e" * 64)
            (root / "jwt_secret").write_text("original legacy jwt")
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, "database_secret_invalid"):
                    loader.configure(root)

    @unittest.skipUnless(os.name == "nt", "Actual DPAPI requires Windows.")
    def test_actual_user_dpapi_roundtrip_excludes_plaintext(self):
        raw = b"fake runtime secret continuity payload"
        sealed = handoff.protect(raw)
        self.assertNotIn(raw, sealed)
        self.assertEqual(handoff.unprotect(sealed), raw)


if __name__ == "__main__":
    unittest.main()
