"""Offline tests: no Docker daemon, host, credentials or Teams calls."""
import importlib.util
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("diagnose_dev", ROOT / "scripts/diagnose_pc24x7_public_dev.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SHA = "a" * 40
IDS = {"api": "a" * 64, "frontend": "b" * 64, "nginx": "c" * 64}


def metadata(service, project="reqsys-dev"):
    return {
        "project": project, "service": service, "state": "running",
        "exit_code": 0, "oom_killed": False, "restart_count": 0, "health": "healthy",
    }


class DiagnosticTests(unittest.TestCase):
    def run_fixture(self, replace=None, invoke=None):
        calls = []

        def capture(args):
            calls.append(args)
            if replace:
                result = replace(args)
                if result is not None:
                    return result
            if args[0] == "inspect":
                service = next(key for key, value in IDS.items() if value == args[-1])
                return json.dumps(metadata(service))
            if args[:2] == ["ps", "--filter"]:
                return IDS["api"]
            if args[:2] == ["ps", "-a"]:
                service = args[-3].split("=")[-1]
                return IDS[service]
            self.fail("Unexpected command")

        with patch.object(MODULE.os, "name", "nt"), patch.object(
            MODULE.socket, "gethostname", return_value=MODULE.HOST
        ), patch.object(MODULE, "_verify_docker_target"), patch.object(MODULE, "_capture", side_effect=capture):
            result = invoke() if invoke else MODULE.diagnose("dev", SHA)
        return result, calls

    def test_stdout_only_success_has_no_writes_or_state_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "existing-evidence.json"
            marker.write_text("preserve")
            def snapshot():
                return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            before = snapshot()
            stream = io.StringIO()
            argv = ["diagnose", "--environment", "dev", "--expected-sha", SHA, "--stdout-only"]
            with patch.object(MODULE.Path, "cwd", return_value=root), patch.object(sys, "argv", argv), redirect_stdout(stream), patch.object(
                MODULE, "_write_evidence", side_effect=AssertionError("unexpected evidence write")
            ) as writer, patch("builtins.open", side_effect=AssertionError("unexpected open")), patch.object(
                MODULE.Path, "open", side_effect=AssertionError("unexpected path open")
            ), patch.object(MODULE.Path, "mkdir", side_effect=AssertionError("unexpected mkdir")):
                code, calls = self.run_fixture(invoke=MODULE.main)
            self.assertEqual(code, 0)
            writer.assert_not_called()
            self.assertEqual(before, snapshot())
            self.assertEqual(list(root.iterdir()), [marker])
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["status"], "diagnostic_collected")
            self.assertEqual(len(payload["containers"]), 3)
            self.assertFalse(payload["runtime_sha_verified"])
            self.assertTrue(all(call[0] in {"ps", "inspect"} for call in calls))

    def test_stdout_only_blocked_preserves_exit_and_no_file(self):
        stream = io.StringIO()
        argv = ["diagnose", "--environment", "dev", "--expected-sha", SHA, "--stdout-only"]
        with patch.object(sys, "argv", argv), redirect_stdout(stream), patch.object(
            MODULE, "diagnose", side_effect=MODULE.DiagnosticError("host_not_allowed")
        ), patch.object(MODULE, "_write_evidence") as writer:
            self.assertEqual(MODULE.main(), 1)
        writer.assert_not_called()
        self.assertEqual(json.loads(stream.getvalue())["reason"], "host_not_allowed")

    def test_stdout_cli_subprocess_leaves_working_directory_unchanged(self):
        if os.name == "nt":
            self.skipTest("Linux offline host-negative integration; never call real Docker on Windows")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "scripts/diagnose_pc24x7_public_dev.py"
            script.parent.mkdir()
            script.write_bytes((ROOT / "scripts/diagnose_pc24x7_public_dev.py").read_bytes())
            before = {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None for p in root.rglob("*")}
            result = subprocess.run([
                sys.executable, "-B", str(script),
                "--environment", "dev", "--expected-sha", SHA, "--stdout-only",
            ], cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)["reason"], "host_not_allowed")
            after = {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None for p in root.rglob("*")}
            self.assertEqual(before, after)
            self.assertFalse(list(root.rglob("__pycache__")))

    def test_output_mode_still_writes_exclusive_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "artifacts/pc24x7-dev-diagnostic/test.json"
            payload = {"status": "diagnostic_collected", "containers": []}
            argv = ["diagnose", "--environment", "dev", "--expected-sha", SHA, "--output", str(output)]
            with patch.object(MODULE.Path, "cwd", return_value=root), patch.object(sys, "argv", argv), patch.object(
                MODULE, "diagnose", return_value=payload
            ), redirect_stdout(io.StringIO()):
                self.assertEqual(MODULE.main(), 0)
                self.assertEqual(json.loads(output.read_text()), payload)
                self.assertEqual(MODULE.main(), 1)
                self.assertEqual(json.loads(output.read_text()), payload)

    def test_destination_required_and_mutually_exclusive_before_docker(self):
        base = ["diagnose", "--environment", "dev", "--expected-sha", SHA]
        for extra in ([], ["--stdout-only", "--output", "evidence.json"]):
            with self.subTest(extra=extra), patch.object(sys, "argv", base + extra), patch.object(
                MODULE, "diagnose"
            ) as diagnose, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    MODULE.main()
                self.assertEqual(raised.exception.code, 2)
                diagnose.assert_not_called()

    def test_dev_read_only_and_redacted(self):
        result, calls = self.run_fixture()
        self.assertEqual(result["status"], "diagnostic_collected")
        self.assertFalse(result["runtime_mutated"])
        self.assertFalse(result["runtime_sha_verified"])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertEqual(len(result["containers"]), 3)
        self.assertTrue(all(call[0] in {"ps", "inspect"} for call in calls))
        self.assertTrue(all(call[-1] in IDS.values() for call in calls if call[0] == "logs"))
        self.assertFalse(result["raw_logs_collected"])
        self.assertNotIn(".Config.Env", MODULE.INSPECT_FORMAT)
        self.assertNotIn(".State.Health.Log", MODULE.INSPECT_FORMAT)

    def test_production_environment_refused_before_docker(self):
        with patch.object(MODULE, "_capture") as capture:
            with self.assertRaisesRegex(MODULE.DiagnosticError, "environment_must_be_dev"):
                MODULE.diagnose("prod", SHA)
            capture.assert_not_called()

    def test_production_container_refused_before_logs(self):
        calls = []
        def replace(args):
            calls.append(args)
            if args[0] == "inspect":
                return json.dumps(metadata("api", "reqsys-prod"))
            return None
        with self.assertRaisesRegex(MODULE.DiagnosticError, "non_dev_or_unexpected_target"):
            self.run_fixture(replace)
        self.assertFalse(any(call[0] == "logs" for call in calls))

    def test_ambiguous_api_refused(self):
        with self.assertRaisesRegex(MODULE.DiagnosticError, "dev_api_8210_not_unique"):
            self.run_fixture(lambda args: IDS["api"] + "\n" + IDS["frontend"] if args[:2] == ["ps", "--filter"] else None)

    def test_identity_change_refused(self):
        def replace(args):
            if args[0] == "inspect" and args[-1] == IDS["frontend"]:
                return json.dumps(metadata("api"))
            return None
        with self.assertRaisesRegex(MODULE.DiagnosticError, "container_identity_changed"):
            self.run_fixture(replace)

    def test_docker_failure_redacts_stderr(self):
        with patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(
            returncode=1, stdout="", stderr="SECRET=private"
        )):
            with self.assertRaisesRegex(MODULE.DiagnosticError, "^docker_read_failed$"):
                MODULE._capture(["ps"])

    def test_malformed_metadata_fails_closed(self):
        for field, value in (("project", []), ("state", []), ("health", []), ("exit_code", True)):
            item = metadata("api")
            item[field] = value
            with self.subTest(field=field), patch.object(MODULE, "_capture", return_value=json.dumps(item)):
                with self.assertRaises(MODULE.DiagnosticError):
                    MODULE._inspect(IDS["api"])
        item = metadata("api")
        del item["health"]
        with patch.object(MODULE, "_capture", return_value=json.dumps(item)):
            with self.assertRaises(MODULE.DiagnosticError):
                MODULE._inspect(IDS["api"])

    def test_replaced_api_refused(self):
        def replace(args):
            if args[:2] == ["ps", "-a"] and "service=api" in " ".join(args):
                return "d" * 64
            return None
        with self.assertRaisesRegex(MODULE.DiagnosticError, "api_identity_changed"):
            self.run_fixture(replace)

    def test_disappeared_api_refused(self):
        def replace(args):
            if args[:2] == ["ps", "-a"] and "service=api" in " ".join(args):
                return ""
            return None
        with self.assertRaisesRegex(MODULE.DiagnosticError, "api_identity_changed"):
            self.run_fixture(replace)

    def test_windows_reparse_point_refused(self):
        with patch.object(MODULE.Path, "lstat", return_value=SimpleNamespace(st_mode=0o40755, st_file_attributes=0x400)):
            with self.assertRaisesRegex(MODULE.DiagnosticError, "evidence_symlink_blocked"):
                MODULE._reject_links(Path("artifacts/pc24x7-dev-diagnostic/test.json"))

    def test_evidence_is_exclusive_and_confined(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(MODULE.Path, "cwd", return_value=Path(directory)):
            root = Path(directory)
            output = root / "artifacts/pc24x7-dev-diagnostic/test.json"
            MODULE._write_evidence(output, {"status": "tested"})
            with self.assertRaisesRegex(MODULE.DiagnosticError, "evidence_already_exists"):
                MODULE._write_evidence(output, {})
            self.assertEqual(json.loads(output.read_text())["status"], "tested")
            with self.assertRaises(MODULE.DiagnosticError):
                MODULE._write_evidence(root / "compose.json", {})
            with self.assertRaises(MODULE.DiagnosticError):
                MODULE._write_evidence(root / "artifacts/pc24x7-dev-diagnostic/.env", {})

    def test_unknown_project_refused(self):
        with patch.object(MODULE, "_capture", return_value=json.dumps(metadata("api", "unknown"))):
            with self.assertRaisesRegex(MODULE.DiagnosticError, "non_dev_or_unexpected_target"):
                MODULE._inspect(IDS["api"])

    def test_invalid_host_refused_before_docker(self):
        with patch.object(MODULE.os, "name", "posix"), patch.object(MODULE, "_capture") as capture:
            with self.assertRaisesRegex(MODULE.DiagnosticError, "host_not_allowed"):
                MODULE.diagnose("dev", SHA)
            capture.assert_not_called()

    def test_remote_environment_overrides_block_before_any_command(self):
        for key in ("DOCKER_HOST", "DOCKER_CONTEXT"):
            with self.subTest(key=key), patch.dict(MODULE.os.environ, {key: "remote-prod"}), patch.object(MODULE.subprocess, "run") as run:
                with self.assertRaisesRegex(MODULE.DiagnosticError, "docker_target_override_blocked"):
                    MODULE._verify_docker_target()
                run.assert_not_called()

    def test_active_remote_context_refused_without_daemon_query(self):
        with patch.dict(MODULE.os.environ, {}, clear=True), patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(
            returncode=0, stdout=json.dumps("tcp://production:2376"), stderr=""
        )) as run:
            with self.assertRaisesRegex(MODULE.DiagnosticError, "docker_context_not_local_dev"):
                MODULE._verify_docker_target()
            self.assertEqual(run.call_args.args[0][:3], ["docker", "context", "inspect"])
            self.assertEqual(run.call_count, 1)

    def test_local_context_accepted_and_daemon_endpoint_pinned(self):
        with patch.dict(MODULE.os.environ, {}, clear=True), patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(
            returncode=0, stdout=json.dumps(MODULE.DOCKER_ENDPOINT), stderr=""
        )) as run:
            MODULE._verify_docker_target()
            MODULE._capture(["ps"])
            self.assertEqual(run.call_args.args[0], ["docker", "--host", MODULE.DOCKER_ENDPOINT, "ps"])

    def test_windows_default_local_context_accepted_but_daemon_remains_pinned(self):
        default_endpoint = "npipe:////./pipe/docker_engine"
        results = [
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(default_endpoint),
                stderr="",
            ),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
        ]
        with patch.dict(MODULE.os.environ, {}, clear=True), patch.object(
            MODULE.subprocess,
            "run",
            side_effect=results,
        ) as run:
            MODULE._verify_docker_target()
            MODULE._capture(["ps"])
            self.assertEqual(
                run.call_args_list[0].args[0][:3],
                ["docker", "context", "inspect"],
            )
            self.assertEqual(
                run.call_args_list[1].args[0],
                ["docker", "--host", MODULE.DOCKER_ENDPOINT, "ps"],
            )

    def test_arbitrary_local_named_pipe_context_is_refused(self):
        result = SimpleNamespace(
            returncode=0,
            stdout=json.dumps("npipe:////./pipe/unapprovedEngine"),
            stderr="",
        )
        with patch.dict(MODULE.os.environ, {}, clear=True), patch.object(
            MODULE.subprocess,
            "run",
            return_value=result,
        ), self.assertRaisesRegex(
            MODULE.DiagnosticError,
            "docker_context_not_local_dev",
        ):
            MODULE._verify_docker_target()


if __name__ == "__main__":
    unittest.main()


