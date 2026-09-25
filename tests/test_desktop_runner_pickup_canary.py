from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "desktop_runner_pickup_canary.py"
SPEC = importlib.util.spec_from_file_location("desktop_runner_pickup_canary", SCRIPT)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class DesktopRunnerPickupCanaryTests(unittest.TestCase):
    def test_exact_desktop_pickup_passes(self):
        env = {
            "OBSERVED_RUNNER_NAME": "DESKTOP-PDQK954",
            "OBSERVED_RUNNER_OS": "Windows",
            "OBSERVED_RUNNER_ARCH": "X64",
        }
        with (
            patch.object(m.socket, "gethostname", return_value="DESKTOP-PDQK954"),
            patch.dict(m.os.environ, env, clear=False),
        ):
            result = m.validate_environment()
        self.assertTrue(result["ok"])
        self.assertTrue(result["physical_pickup_proven"])

    def test_wrong_host_fails_closed(self):
        env = {
            "OBSERVED_RUNNER_NAME": "DESKTOP-PDQK954",
            "OBSERVED_RUNNER_OS": "Windows",
            "OBSERVED_RUNNER_ARCH": "X64",
        }
        with (
            patch.object(m.socket, "gethostname", return_value="NOTERI"),
            patch.dict(m.os.environ, env, clear=False),
        ):
            with self.assertRaisesRegex(m.CanaryError, "host_mismatch"):
                m.validate_environment()

    def test_wrong_runner_name_fails_closed(self):
        env = {
            "OBSERVED_RUNNER_NAME": "other",
            "OBSERVED_RUNNER_OS": "Windows",
            "OBSERVED_RUNNER_ARCH": "X64",
        }
        with (
            patch.object(m.socket, "gethostname", return_value="DESKTOP-PDQK954"),
            patch.dict(m.os.environ, env, clear=False),
        ):
            with self.assertRaisesRegex(m.CanaryError, "runner_name_mismatch"):
                m.validate_environment()


if __name__ == "__main__":
    unittest.main()
