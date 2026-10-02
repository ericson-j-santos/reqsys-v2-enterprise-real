"""Testa isolamento, validacao de segredo e inicializacao idempotente."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

startup = module(ROOT / "infra/self-hosted/start_api.py")
initializer = module(ROOT / "scripts/init_self_hosted_secrets.py")

class SelfHostedTests(unittest.TestCase):
    def test_missing_and_malformed_secret_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                startup.read_secret(root, "jwt_secret")
            (root / "jwt_secret").write_text("changeme")
            with self.assertRaises(ValueError):
                startup.read_secret(root, "jwt_secret")

    def test_initializer_preserves_existing_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "secrets"
            self.assertEqual(initializer.initialize(root), 3)
            original = {p.name: p.read_bytes() for p in root.iterdir()}
            self.assertEqual(initializer.initialize(root), 0)
            self.assertEqual(original, {p.name: p.read_bytes() for p in root.iterdir()})
            for name in original:
                self.assertEqual(len(startup.read_secret(root, name)), 64)

    def test_no_partial_environment_when_jwt_invalid(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            (root / "db_app_password").write_text("a" * 64)
            (root / "jwt_secret").write_text("invalid")
            with self.assertRaises(ValueError):
                startup.configure(root)
            self.assertNotIn("DATABASE_URL", os.environ)

    def test_database_uses_unprivileged_role(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            (root / "db_app_password").write_text("a" * 64)
            (root / "jwt_secret").write_text("b" * 64)
            startup.configure(root)
            self.assertIn("://reqsys_app:", os.environ["DATABASE_URL"])
            self.assertEqual(os.environ["JWT_SECRET"], "b" * 64)

    @unittest.skipUnless(os.name == "posix", "Permissoes POSIX apenas em Linux")
    def test_public_secret_directory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "secrets"
            root.mkdir(mode=0o755)
            with self.assertRaises(ValueError):
                initializer.initialize(root)

if __name__ == "__main__":
    unittest.main()
