from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


launcher = load("rdc_headless_uac_launcher")
admin = load("rdc_headless_admin_apply")


def test_launcher_rejects_wrong_host_and_confirmation():
    with mock.patch.object(launcher.socket, "gethostname", return_value="OTHER"):
        try:
            launcher.validate("OTHER", "nt", launcher.LAUNCH_CONFIRM)
        except RuntimeError as exc:
            assert str(exc) == "host_not_allowlisted"
        else:
            raise AssertionError("host should be rejected")

    try:
        launcher.validate(launcher.HOST, "nt", "wrong")
    except RuntimeError as exc:
        assert str(exc) == "confirmation_invalid"
    else:
        raise AssertionError("confirmation should be rejected")


def test_launcher_builds_only_fixed_admin_helper(tmp_path: Path):
    with mock.patch.object(launcher, "__file__", str(tmp_path / "rdc_headless_uac_launcher.py")):
        args = launcher.build_args(Path(r"C:\rules"), "a" * 40)
    assert "rdc_headless_admin_apply.py" in args
    assert "C:\\rules" in args or "C:\rules" in args
    assert "a" * 40 in args
    assert launcher.APPLY_CONFIRM in args


def test_admin_apply_requires_admin_before_mutation(tmp_path: Path):
    with (
        mock.patch.object(admin.socket, "gethostname", return_value=admin.HOST),
        mock.patch.object(admin.os, "name", "nt"),
        mock.patch.object(admin, "is_admin", return_value=False),
    ):
        try:
            admin.apply(tmp_path, "a" * 40, admin.CONFIRM)
        except RuntimeError as exc:
            assert str(exc) == "administrative_token_required"
        else:
            raise AssertionError("non-admin must be rejected")
