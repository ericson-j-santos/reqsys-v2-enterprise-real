"""Reparo reversivel da referencia Python do supervisor Noteri; nao inicia processos."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import socket
import stat
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(r"C:\dev\chatgpt-workers\reqsys-orchestrator-24x7-runtime")
URL = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
ARCHIVE_SHA = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
CONFIRM = "REPAIR-NOTERI-SUPERVISOR-PYTHON-DEV"
MAX_BYTES = 32 * 1024 * 1024
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
COMMAND = re.compile(rb'(?m)^"([^"\r\n]+python\.exe)" -m scripts\.service_supervisor --config "([^"\r\n]+)"\r?$')


class Blocked(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def no_links(path: Path) -> None:
    for part in (path, *path.parents):
        if part.exists() and (part.is_symlink() or getattr(part.lstat(), "st_file_attributes", 0) & 1024):
            raise Blocked("path_link_rejected")


def read_bytes(path: Path, limit: int = 131072) -> bytes:
    no_links(path)
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > limit:
        raise Blocked("file_size_or_type_invalid")
    value = path.read_bytes()
    if len(value) > limit:
        raise Blocked("file_size_invalid")
    return value


def obj(path: Path) -> dict:
    value = json.loads(read_bytes(path).decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise Blocked("json_object_required")
    return value


def atomic_write(path: Path, content: bytes) -> None:
    no_links(path)
    target = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with target.open("xb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(target, path)
    finally:
        if target.exists():
            target.unlink()


def replace_interpreter(original: bytes, executable: Path, config: Path) -> bytes:
    matches = list(COMMAND.finditer(original))
    if len(matches) != 1 or Path(matches[0].group(2).decode("utf-8")) != config:
        raise Blocked("startup_command_not_unique_or_wrong_config")
    new = str(executable).encode("utf-8")
    if any(c in new for c in (b'"', b"\r", b"\n", b"%", b"&", b"|")):
        raise Blocked("executable_path_invalid")
    match = matches[0]
    return original[:match.start(1)] + new + original[match.end(1):]


def extract_checked(raw: bytes, destination: Path, expected: str = ARCHIVE_SHA) -> None:
    if len(raw) > MAX_BYTES or digest(raw) != expected:
        raise Blocked("python_archive_digest_mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        total = 0
        seen: set[str] = set()
        for entry in entries:
            name = entry.filename
            if not name or name in (".", "..") or any(c in name for c in ("/", "\\", ":")):
                raise Blocked("python_archive_path_invalid")
            if name.casefold() in seen or stat.S_ISLNK(entry.external_attr >> 16):
                raise Blocked("python_archive_duplicate_or_link")
            seen.add(name.casefold())
            total += entry.file_size
            if total > 96 * 1024 * 1024:
                raise Blocked("python_archive_expansion_limit")
        for entry in entries:
            (destination / entry.filename).write_bytes(archive.read(entry))


def verify_bundle(bundle: Path) -> None:
    # O ZIP oficial pinado e a fonte independente; o manifesto local nao se autoatesta.
    raw = read_bytes(bundle / "distribution.zip", MAX_BYTES)
    if digest(raw) != ARCHIVE_SHA:
        raise Blocked("python_bundle_archive_mismatch")
    manifest = obj(bundle / "integrity.json")
    files = manifest.get("files")
    if manifest.get("archive_sha256") != ARCHIVE_SHA or not isinstance(files, dict) or not files:
        raise Blocked("python_bundle_manifest_invalid")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        expected = {item.filename: digest(archive.read(item)) for item in archive.infolist()}
    expected["python312._pth"] = digest(("python312.zip\n.\n" + str(ROOT) + "\n").encode("utf-8"))
    if files != expected:
        raise Blocked("python_bundle_manifest_mismatch")
    observed = {p.name for p in bundle.iterdir()}
    if observed != set(files) | {"integrity.json", "distribution.zip"}:
        raise Blocked("python_bundle_file_set_changed")
    for name, expected_hash in files.items():
        if "/" in name or "\\" in name or ":" in name or name in (".", ".."):
            raise Blocked("python_manifest_path_invalid")
        if digest(read_bytes(bundle / name, 96 * 1024 * 1024)) != expected_hash:
            raise Blocked("python_bundle_integrity_mismatch")


def ensure_bundle(bundle: Path) -> None:
    no_links(bundle)
    if bundle.exists():
        verify_bundle(bundle)
        return
    bundle.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(URL, timeout=30) as response:
        if response.status != 200 or response.geturl() != URL:
            raise Blocked("python_download_source_invalid")
        raw = response.read(MAX_BYTES + 1)
    with tempfile.TemporaryDirectory(prefix="python-stage-", dir=bundle.parent) as temporary:
        stage = Path(temporary)
        extract_checked(raw, stage)
        for name in ("python.exe", "python312.dll", "python312.zip", "python312._pth"):
            if not (stage / name).is_file():
                raise Blocked("python_bundle_incomplete")
        pth = stage / "python312._pth"
        pth.write_bytes(("python312.zip\n.\n" + str(ROOT) + "\n").encode("utf-8"))
        files = {p.name: digest(p.read_bytes()) for p in stage.iterdir() if p.is_file()}
        (stage / "integrity.json").write_text(json.dumps({
            "archive_sha256": ARCHIVE_SHA, "files": files,
        }, sort_keys=True) + "\n", encoding="utf-8")
        (stage / "distribution.zip").write_bytes(raw)
        verify_bundle(stage)
        if bundle.exists():
            raise Blocked("python_bundle_concurrent_install")
        os.rename(stage, bundle)


def validate_python(bundle: Path) -> None:
    verify_bundle(bundle)
    executable = str(bundle / "python.exe")
    version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10)
    if version.returncode or version.stdout.strip() != "Python 3.12.10":
        raise Blocked("dedicated_python_version_invalid")
    for module in ("scripts.service_supervisor", "orchestrator.worker_agent"):
        result = subprocess.run([executable, "-B", "-m", module, "--help"],
                                cwd=ROOT, capture_output=True, timeout=15)
        if result.returncode:
            raise Blocked("dedicated_python_import_probe_failed")


def repair_reference(wrapper: Path, bundle: Path, records: Path, config: Path,
                     expected_wrapper_sha: str, prepare=ensure_bundle, validate=validate_python) -> dict:
    no_links(records)
    before = read_bytes(wrapper)
    receipt_path, backup_path = records / "receipt.json", records / "startup.original.cmd"
    if receipt_path.exists():
        receipt = obj(receipt_path)
        backup = read_bytes(backup_path)
        if digest(backup) != expected_wrapper_sha or receipt.get("original_sha256") != expected_wrapper_sha:
            raise Blocked("backup_identity_mismatch")
        expected = replace_interpreter(backup, bundle / "python.exe", config)
        if before == expected:
            validate(bundle)
            return {"ok": True, "state": "already_applied", "wrapper_sha256": digest(before)}
        if digest(before) != expected_wrapper_sha:
            raise Blocked("startup_changed_after_repair")
    if digest(before) != expected_wrapper_sha:
        raise Blocked("startup_lease_mismatch")
    replacement = replace_interpreter(before, bundle / "python.exe", config)
    prepare(bundle)
    validate(bundle)
    if read_bytes(wrapper) != before:
        raise Blocked("startup_changed_during_preparation")
    records.mkdir(parents=True, exist_ok=True)
    if backup_path.exists() and read_bytes(backup_path) != before:
        raise Blocked("existing_backup_mismatch")
    if not backup_path.exists():
        with backup_path.open("xb") as out:
            out.write(before)
            out.flush()
            os.fsync(out.fileno())
    receipt = {"original_sha256": digest(before), "repaired_sha256": digest(replacement),
               "archive_sha256": ARCHIVE_SHA, "process_started": False}
    atomic_write(receipt_path, (json.dumps(receipt, sort_keys=True) + "\n").encode())
    try:
        atomic_write(wrapper, replacement)
        if read_bytes(wrapper) != replacement:
            raise Blocked("startup_readback_mismatch")
    except BaseException:
        current = read_bytes(wrapper)
        if current == replacement:
            atomic_write(wrapper, before)
        raise
    return {"ok": True, "state": "reference_repaired", "wrapper_sha256": digest(replacement)}


def rollback_reference(wrapper: Path, records: Path) -> dict:
    receipt = obj(records / "receipt.json")
    backup = read_bytes(records / "startup.original.cmd")
    current = read_bytes(wrapper)
    if digest(backup) != receipt.get("original_sha256"):
        raise Blocked("backup_integrity_mismatch")
    if current == backup:
        return {"ok": True, "state": "already_rolled_back"}
    if digest(current) != receipt.get("repaired_sha256"):
        raise Blocked("rollback_would_overwrite_external_change")
    atomic_write(wrapper, backup)
    if read_bytes(wrapper) != backup:
        raise Blocked("rollback_readback_failed")
    return {"ok": True, "state": "rolled_back"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-runtime-sha", required=True)
    parser.add_argument("--expected-wrapper-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    try:
        if os.name != "nt" or socket.gethostname().casefold() != "noteri" or args.confirm != CONFIRM:
            raise Blocked("host_or_confirmation_invalid")
        if not HEX40.fullmatch(args.expected_sha) or not HEX40.fullmatch(args.expected_runtime_sha):
            raise Blocked("sha_invalid")
        if not HEX64.fullmatch(args.expected_wrapper_sha):
            raise Blocked("wrapper_sha_invalid")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", args.correlation_id):
            raise Blocked("correlation_invalid")
        repo = Path(__file__).resolve().parents[1]
        git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=10)
        if git.returncode or git.stdout.strip() != args.expected_sha:
            raise Blocked("source_sha_mismatch")
        config = ROOT / "service-config.json"
        worker_config = ROOT / "worker-config.json"
        before = {p: read_bytes(p) for p in (config, worker_config, ROOT / "runtime-version.json")}
        service, worker = obj(config), obj(worker_config)
        if obj(ROOT / "runtime-version.json").get("source_sha") != args.expected_runtime_sha:
            raise Blocked("installed_runtime_sha_mismatch")
        if service.get("mode") != "worker" or Path(service.get("install_root", "")) != ROOT:
            raise Blocked("supervisor_identity_mismatch")
        if Path(service.get("worker_config", "")) != worker_config:
            raise Blocked("supervisor_worker_config_mismatch")
        if worker.get("worker_id") != "noteri" or worker.get("endpoint", "").rstrip("/") != "http://DESKTOP-PDQK954:8787":
            raise Blocked("worker_identity_mismatch")
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise Blocked("appdata_missing")
        wrapper = Path(appdata) / "Microsoft/Windows/Start Menu/Programs/Startup/ReqSys-Orchestrator-noteri.cmd"
        bundle = ROOT / "maintenance/python-3.12.10-embed-amd64"
        records = ROOT / "maintenance/python-reference-repair" / args.expected_wrapper_sha
        if not args.rollback and digest(read_bytes(wrapper)) == args.expected_wrapper_sha:
            old_commands = list(COMMAND.finditer(read_bytes(wrapper)))
            if len(old_commands) != 1:
                raise Blocked("startup_command_not_unique")
            old_python = old_commands[0].group(1).decode("utf-8")
            probe = subprocess.run([old_python, "--version"], capture_output=True,
                                   text=True, timeout=10)
            if probe.returncode != 103 or "No Python at" not in probe.stderr:
                raise Blocked("broken_interpreter_precondition_not_confirmed")
        if args.rollback:
            result = rollback_reference(wrapper, records)
        else:
            result = repair_reference(wrapper, bundle, records, config, args.expected_wrapper_sha)
        if any(read_bytes(p) != value for p, value in before.items()):
            raise Blocked("configuration_changed_concurrently")
        result.update({"host": "Noteri", "environment": "dev", "source_sha": args.expected_sha,
                       "runtime_sha": args.expected_runtime_sha, "correlation_id": args.correlation_id,
                       "process_started": False, "profile_changed": False,
                       "administrator_requested": False, "reboot": False})
    except (Blocked, OSError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        reason = str(error) if isinstance(error, Blocked) else type(error).__name__
        print(json.dumps({"ok": False, "reason": reason, "process_started": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
