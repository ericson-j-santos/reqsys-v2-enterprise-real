#!/usr/bin/env python3
"""Execute the recovered standalone v1.0 Baseline92 as an isolated reference.

This runner certifies only the archived standalone reference. It never treats a
successful reference run as compatibility or functional certification of the
currently distributed OCR engine.
"""
from __future__ import annotations

import argparse
import ast
import base64
import copy
from dataclasses import dataclass
import hashlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import socket
import subprocess
import sys
import tarfile
import tempfile
import unittest
from typing import Any, Callable, Iterable


SCHEMA_VERSION = "1.0.0"
CONSUMER_SHA = "f487837fa553a0f5f8af753963539e60a79dbe19"
COMPATIBILITY_AUDIT_SHA = "84b63883004bc7a425dfc72b7ea8b24b68017f16"
INVENTORY_BLOB_SHA1 = "51dbc603e7421bf7117059b5e1ae94cbb0142c1b"
INVENTORY_SHA256 = "e2a73dea8c204f8b36f8c4f49b1fbbb87f8a999deeb0a61c3fed198b47d2c492"
ATTESTATION_SHA256 = "493edc8eaca72062c96afd7f0ec504d4a958d3956c12b7849f8e5c11e6f556fa"
IDS_SHA256 = "5ccf93074b4dafe3964e8c5ab0654ba516a65e1827db1ff5cc4c2fa09c27ec93"
ORIGINAL_ARCHIVE_SHA256 = "2f0afdf3f3b006ec528c270e99574a43a2e0471a7c102688a4d92d4bccc0f32e"
GENERATOR_SHA256 = "e28f14311305247622922abcdf201f3101f5803d2f41b15593061103989830da"
PAYLOAD_SHA256 = "6bd0bdcc48b0cc01be01fd5231cba4d477c2bbb3a90856c0ef8eda1a111d6add"
PRIVATE_SOURCE_REPOSITORY = "ericson-j-santos/ocr-evidence-engine"
PRIVATE_SOURCE_COMMIT = "de075002e14e77f3e69f53a276616d9d8b291bc7"
PRIVATE_SOURCE_PATH = "audit/baseline92/v1.0/gerar_ocr_evidencia.py"
CURRENT_ENGINE_STATUS = "BLOCKED_API_COMPATIBILITY"
FINAL_STATUS = "REFERENCE_STANDALONE_CERTIFIED_CURRENT_ENGINE_BLOCKED"

EXPECTED_TESTS = {
    "tests/test_casos_uso.py": (18, "885b32c0d4003948f05b108ec3b06dcfb5464d9fa9ddf56e7283db27b4d22418"),
    "tests/test_metrica.py": (21, "1aa1b0f0305f648af58f9bb3c043283c1ff80465517ad949ada674a0d746cb50"),
    "tests/test_privacidade.py": (24, "75f4bcd6126f23d5843574fb3545734f220b051adbe2b900be981efdec1b05b1"),
    "tests/test_verificacao.py": (29, "d24f0cc17a219e8b3283e0209083b07e9fbcbb56deabc4b59c5ffb47a552aaf4"),
}

REQUIRED_MODULES = {
    "ocr_evidencia.adaptadores.repositorio_jsonl": "src/ocr_evidencia/adaptadores/repositorio_jsonl.py",
    "ocr_evidencia.aplicacao.casos_uso": "src/ocr_evidencia/aplicacao/casos_uso.py",
    "ocr_evidencia.dominio.divergencia": "src/ocr_evidencia/dominio/divergencia.py",
    "ocr_evidencia.dominio.mascaramento": "src/ocr_evidencia/dominio/mascaramento.py",
    "ocr_evidencia.dominio.medicao": "src/ocr_evidencia/dominio/medicao.py",
    "ocr_evidencia.dominio.metrica": "src/ocr_evidencia/dominio/metrica.py",
    "ocr_evidencia.dominio.verificacao": "src/ocr_evidencia/dominio/verificacao.py",
    "ocr_evidencia.portas.protocolos": "src/ocr_evidencia/portas/protocolos.py",
}

BLOCKED_PROCESS_EVENTS = {
    "os.exec",
    "os.fork",
    "os.forkpty",
    "os.posix_spawn",
    "os.posix_spawnp",
    "os.system",
    "subprocess.Popen",
}
BLOCKED_NETWORK_EVENTS = {
    "socket.bind",
    "socket.connect",
    "socket.connect_ex",
    "socket.getaddrinfo",
    "socket.gethostbyaddr",
    "socket.gethostbyname",
    "socket.gethostbyname_ex",
    "socket.getnameinfo",
    "socket.sendmsg",
    "socket.sendto",
}
NEGATIVE_CONTROL_NAMES = {
    "body_not_executed",
    "duplicate_test_id",
    "false_current_engine_certification",
    "forged_pass_count",
    "missing_execution_case",
    "missing_test_id",
    "replaced_test_id_same_count",
    "replay_divergence",
    "skipped_test",
    "wrong_generator_sha",
    "wrong_payload_sha",
}


class ReferenceError(RuntimeError):
    """Fail-closed validation or execution error."""


@dataclass(frozen=True)
class ParsedReference:
    version: str
    payload: bytes
    manifest: dict[str, str]
    files: dict[str, bytes]


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ReferenceError(reason)


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git_blob_sha1(value: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(value)).encode("ascii") + b"\0" + value).hexdigest()


def _assignment_node(tree: ast.Module, name: str) -> ast.expr:
    matches: list[ast.expr] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                matches.append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            matches.append(node.value)
    require(len(matches) == 1, f"generator_assignment_invalid:{name}")
    return matches[0]


def _literal_assignment(tree: ast.Module, name: str) -> Any:
    try:
        return ast.literal_eval(_assignment_node(tree, name))
    except (ValueError, TypeError, SyntaxError) as error:
        raise ReferenceError(f"generator_literal_invalid:{name}") from error


def _safe_payload_path(name: str) -> PurePosixPath:
    require(bool(name) and "\x00" not in name and "\\" not in name, "payload_path_invalid")
    require(not name.startswith("/") and not name.endswith("/"), f"payload_path_invalid:{name}")
    require(all(part not in {"", ".", ".."} for part in name.split("/")), f"payload_path_invalid:{name}")
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts, f"payload_path_invalid:{name}")
    return path


def validate_attestation(data: dict[str, Any]) -> None:
    require(data.get("schema_version") == SCHEMA_VERSION, "attestation_schema_mismatch")
    require(data.get("scope") == "original_standalone_v1_0_reference_execution", "attestation_scope_mismatch")
    require(
        data.get("correlation_id") == "ocr-baseline92-reference-20261020-f487837f",
        "attestation_correlation_id_mismatch",
    )
    require(data.get("consumer_sha") == CONSUMER_SHA, "attestation_consumer_sha_mismatch")
    require(data.get("compatibility_audit_sha") == COMPATIBILITY_AUDIT_SHA, "attestation_audit_sha_mismatch")

    source = data.get("source", {})
    archive = source.get("original_archive", {})
    generator = source.get("generator", {})
    payload = source.get("payload", {})
    cross = source.get("cross_attestation", {})
    require(archive.get("sha256") == ORIGINAL_ARCHIVE_SHA256, "archive_sha256_mismatch")
    require(archive.get("provider") == "google_drive_private", "archive_provider_mismatch")
    require(archive.get("file_id") == "1eH9VCGcUwcZk3Z0PcP_IjveeB43TMoXs", "archive_file_id_mismatch")
    require(archive.get("name") == "ocr evidencia-1.0.0", "archive_name_mismatch")
    require(archive.get("size_bytes") == 91650 and archive.get("zip_entries") == 37, "archive_inventory_mismatch")
    require(archive.get("uncompressed_bytes") == 183276, "archive_size_mismatch")
    require(archive.get("repository_embedded") is False, "archive_must_not_be_embedded")
    require(archive.get("shared") is False, "archive_sharing_changed")
    require(generator.get("repository") == PRIVATE_SOURCE_REPOSITORY, "generator_repository_mismatch")
    require(generator.get("commit_sha") == PRIVATE_SOURCE_COMMIT, "generator_commit_mismatch")
    require(generator.get("path") == PRIVATE_SOURCE_PATH, "generator_path_mismatch")
    require(generator.get("public_repository_embedded") is False, "generator_publicly_embedded")
    require(generator.get("original_path") == "gerar_ocr_evidencia.py", "generator_original_path_mismatch")
    require(generator.get("version") == "1.0.0", "generator_version_mismatch")
    require(generator.get("size_bytes") == 59136, "generator_size_mismatch")
    require(generator.get("sha256") == GENERATOR_SHA256, "generator_sha256_mismatch")
    require(payload.get("compressed_bytes") == 32703, "payload_compressed_size_mismatch")
    require(payload.get("uncompressed_bytes") == 112199, "payload_uncompressed_size_mismatch")
    require(payload.get("manifest_files") == 24, "payload_manifest_count_mismatch")
    require(payload.get("sha256") == PAYLOAD_SHA256, "payload_sha256_mismatch")
    require(cross.get("declared_generator_v1_0_sha256") == GENERATOR_SHA256, "cross_generator_mismatch")
    require(cross.get("declared_payload_v1_0_sha256") == PAYLOAD_SHA256, "cross_payload_mismatch")
    require(cross.get("declared_tests_v1_0") == 92, "cross_test_count_mismatch")
    require(cross.get("successor_version") == "1.1.0", "cross_successor_version_mismatch")
    require(
        cross.get("successor_html_sha256") == "6576c7a30c9254c18d2af9e919bf2437fc38da01f657af96d12a4332092bd987",
        "cross_successor_html_mismatch",
    )
    require(
        cross.get("successor_report_sha256") == "c794eac440a29a70b4faaf5e55d5064e84d3d8fdbb1f01812036f8596253dd18",
        "cross_successor_report_mismatch",
    )

    baseline = data.get("baseline", {})
    require(baseline.get("expected_cases") == 92, "attestation_case_count_mismatch")
    require(baseline.get("ids_sha256") == IDS_SHA256, "attestation_ids_digest_mismatch")
    tests = baseline.get("tests", {})
    require(set(tests) == set(EXPECTED_TESTS), "attestation_test_set_mismatch")
    for path, (count, digest) in EXPECTED_TESTS.items():
        require(tests[path].get("expected_cases") == count, f"attestation_test_count_mismatch:{path}")
        require(tests[path].get("sha256") == digest, f"attestation_test_sha256_mismatch:{path}")

    claims = data.get("claims", {})
    require(
        claims.get("original_archive_bytes_verified_during_source_recovery") is True,
        "original_archive_recovery_not_attested",
    )
    require(
        claims.get("original_archive_bytes_reverified_by_ci") is False,
        "false_original_archive_ci_reverification",
    )
    require(
        claims.get("original_v1_0_generator_and_payload_bytes_verified") is True,
        "original_generator_payload_not_attested",
    )
    require(claims.get("private_source_ref_verified") is True, "private_source_ref_not_attested")
    require(claims.get("reference_execution_required") is True, "reference_execution_not_required")
    require(claims.get("current_engine_baseline_functional_certified") is False, "false_current_engine_certification")
    require(claims.get("current_engine_status") == CURRENT_ENGINE_STATUS, "current_engine_status_changed")
    require(claims.get("semantic_equivalence_to_current_engine") == "NOT_PROVEN", "false_semantic_equivalence")
    require(claims.get("concurrent_or_distributed_idempotency_certified") is False, "false_concurrency_certification")


def load_attestation(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    require(sha256_bytes(raw) == ATTESTATION_SHA256, "attestation_bytes_changed")
    data = json.loads(raw)
    validate_attestation(data)
    return data, sha256_bytes(raw)


def _inventory_ids(group: dict[str, Any]) -> list[str]:
    return [
        f"{group['path']}::{class_name}::{method}"
        for class_name, methods in group["cases"].items()
        for method in methods
    ]


def validate_ids(ids: Iterable[str]) -> list[str]:
    ordered = sorted(ids)
    require(len(ordered) == 92, "baseline_id_count_changed")
    require(len(set(ordered)) == 92, "baseline_ids_duplicated")
    digest = sha256_bytes(json.dumps(ordered, separators=(",", ":")).encode("utf-8"))
    require(digest == IDS_SHA256, "baseline_ids_changed")
    return ordered


def load_inventory(path: Path) -> tuple[dict[str, Any], list[str], str]:
    raw = path.read_bytes()
    require(git_blob_sha1(raw) == INVENTORY_BLOB_SHA1, "inventory_bytes_changed")
    require(sha256_bytes(raw) == INVENTORY_SHA256, "inventory_sha256_changed")
    data = json.loads(raw)
    require(data.get("schema_version") == SCHEMA_VERSION, "inventory_schema_mismatch")
    require(data.get("expected_cases") == 92, "inventory_case_count_changed")
    require(data.get("consumer_sha") == CONSUMER_SHA, "inventory_consumer_sha_mismatch")
    require(data.get("baseline_original_v1_0_bytes_verified") is False, "historical_inventory_rewritten")
    require(data.get("baseline_functional_certified") is False, "historical_inventory_false_certification")
    groups = data.get("groups", [])
    require(len(groups) == 4, "inventory_group_count_changed")
    by_path = {group.get("path"): group for group in groups}
    require(set(by_path) == set(EXPECTED_TESTS), "inventory_test_set_changed")
    ids: list[str] = []
    for test_path, (expected_count, expected_digest) in EXPECTED_TESTS.items():
        group = by_path[test_path]
        require(group.get("expected_cases") == expected_count, f"inventory_group_count_changed:{test_path}")
        require(group.get("sha256") == expected_digest, f"inventory_test_sha256_changed:{test_path}")
        group_ids = _inventory_ids(group)
        require(len(group_ids) == expected_count, f"inventory_group_ids_changed:{test_path}")
        ids.extend(group_ids)
    return data, validate_ids(ids), sha256_bytes(raw)


def _ids_from_sources(files: dict[str, bytes]) -> list[str]:
    ids: list[str] = []
    for test_path, (expected_count, expected_digest) in EXPECTED_TESTS.items():
        raw = files.get(test_path)
        require(raw is not None, f"reference_test_missing:{test_path}")
        require(sha256_bytes(raw) == expected_digest, f"reference_test_sha256_mismatch:{test_path}")
        try:
            tree = ast.parse(raw.decode("utf-8"), filename=test_path)
        except (UnicodeDecodeError, SyntaxError) as error:
            raise ReferenceError(f"reference_test_parse_failed:{test_path}") from error
        group_ids = [
            f"{test_path}::{node.name}::{member.name}"
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test")
            for member in node.body
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and member.name.startswith("test_")
        ]
        require(len(group_ids) == expected_count, f"reference_test_count_mismatch:{test_path}")
        ids.extend(group_ids)
    return validate_ids(ids)


def parse_reference(generator_path: Path, attestation: dict[str, Any]) -> ParsedReference:
    raw = generator_path.read_bytes()
    require(len(raw) == attestation["source"]["generator"]["size_bytes"], "generator_size_changed")
    require(sha256_bytes(raw) == GENERATOR_SHA256, "generator_bytes_changed")
    try:
        tree = ast.parse(raw.decode("utf-8"), filename=generator_path.name)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise ReferenceError("generator_parse_failed") from error

    version = _literal_assignment(tree, "__version__")
    package_name = _literal_assignment(tree, "NOME_PACOTE")
    declared_payload_sha = _literal_assignment(tree, "SHA256_PAYLOAD")
    manifest_node = _assignment_node(tree, "MANIFESTO")
    manifest = _literal_assignment(tree, "MANIFESTO")
    payload_chunks = _literal_assignment(tree, "_PAYLOAD_B64")
    require(version == "1.0.0" and package_name == "ocr_evidencia", "generator_identity_changed")
    require(declared_payload_sha == PAYLOAD_SHA256, "generator_payload_declaration_changed")
    require(isinstance(manifest_node, ast.Dict), "generator_manifest_not_literal_dict")
    literal_keys = [ast.literal_eval(key) for key in manifest_node.keys]
    require(len(literal_keys) == len(set(literal_keys)), "generator_manifest_duplicate_path")
    require(isinstance(manifest, dict) and len(manifest) == 24, "generator_manifest_changed")
    require(
        isinstance(payload_chunks, (str, tuple, list)) and payload_chunks,
        "generator_payload_chunks_invalid",
    )
    if isinstance(payload_chunks, str):
        encoded_payload = payload_chunks
    else:
        require(
            all(isinstance(chunk, str) and chunk for chunk in payload_chunks),
            "generator_payload_chunk_invalid",
        )
        encoded_payload = "".join(payload_chunks)
    for name, digest in manifest.items():
        require(isinstance(name, str) and isinstance(digest, str), "generator_manifest_entry_invalid")
        _safe_payload_path(name)
        require(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "generator_manifest_digest_invalid")

    try:
        payload = base64.b64decode(encoded_payload, validate=True)
    except Exception as error:
        raise ReferenceError("generator_payload_base64_invalid") from error
    require(len(payload) == 32703, "payload_size_changed")
    require(sha256_bytes(payload) == PAYLOAD_SHA256, "payload_bytes_changed")

    files: dict[str, bytes] = {}
    total_size = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            members = archive.getmembers()
            require(len(members) == 24, "payload_member_count_changed")
            for member in members:
                name = str(_safe_payload_path(member.name))
                require(name not in files, f"payload_duplicate_member:{name}")
                require(member.isfile() and not member.issym() and not member.islnk(), f"payload_member_type_denied:{name}")
                require(0 <= member.size <= 1_000_000, f"payload_member_size_denied:{name}")
                stream = archive.extractfile(member)
                require(stream is not None, f"payload_member_unreadable:{name}")
                content = stream.read(1_000_001)
                require(len(content) == member.size, f"payload_member_size_mismatch:{name}")
                files[name] = content
                total_size += len(content)
    except tarfile.TarError as error:
        raise ReferenceError("payload_tar_invalid") from error
    require(total_size == 112199, "payload_uncompressed_size_changed")
    require(set(files) == set(manifest), "payload_manifest_file_set_mismatch")
    for name, expected in manifest.items():
        require(sha256_bytes(files[name]) == expected, f"payload_manifest_digest_mismatch:{name}")
    _ids_from_sources(files)
    return ParsedReference(version=version, payload=payload, manifest=manifest, files=files)


def extract_reference(reference: ParsedReference, destination: Path) -> Path:
    require(not destination.exists(), "reference_destination_exists")
    destination.mkdir(parents=True)
    for name, content in sorted(reference.files.items()):
        relative = _safe_payload_path(name)
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        require(target.resolve().is_relative_to(destination.resolve()), f"reference_path_escape:{name}")
        with target.open("xb") as stream:
            stream.write(content)
    observed = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    require(observed == set(reference.manifest), "reference_extraction_inventory_mismatch")
    return destination


def _flatten_suite(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    tests: list[unittest.TestCase] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            tests.extend(_flatten_suite(item))
        else:
            require(isinstance(item, unittest.TestCase), "unexpected_unittest_item")
            tests.append(item)
    return tests


class RecordingResult(unittest.TestResult):
    def __init__(self, ids: dict[int, str]) -> None:
        super().__init__()
        self.ids = ids
        self.outcomes: dict[str, str] = {}

    def startTest(self, test: unittest.TestCase) -> None:  # noqa: N802
        super().startTest(test)
        self.outcomes[self.ids[id(test)]] = "STARTED"

    def addSuccess(self, test: unittest.TestCase) -> None:  # noqa: N802
        super().addSuccess(test)
        self.outcomes[self.ids[id(test)]] = "PASSED"

    def addFailure(self, test: unittest.TestCase, err: tuple[type[BaseException], BaseException, Any]) -> None:  # noqa: N802
        super().addFailure(test, err)
        self.outcomes[self.ids[id(test)]] = "FAILED"

    def addError(self, test: unittest.TestCase, err: tuple[type[BaseException], BaseException, Any]) -> None:  # noqa: N802
        super().addError(test, err)
        self.outcomes[self.ids[id(test)]] = "ERROR"

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:  # noqa: N802
        super().addSkip(test, reason)
        self.outcomes[self.ids[id(test)]] = "SKIPPED"

    def addExpectedFailure(self, test: unittest.TestCase, err: tuple[type[BaseException], BaseException, Any]) -> None:  # noqa: N802
        super().addExpectedFailure(test, err)
        self.outcomes[self.ids[id(test)]] = "EXPECTED_FAILURE"

    def addUnexpectedSuccess(self, test: unittest.TestCase) -> None:  # noqa: N802
        super().addUnexpectedSuccess(test)
        self.outcomes[self.ids[id(test)]] = "UNEXPECTED_SUCCESS"

    def addSubTest(self, test: unittest.TestCase, subtest: unittest.TestCase, err: tuple[type[BaseException], BaseException, Any] | None) -> None:  # noqa: N802
        super().addSubTest(test, subtest, err)
        if err is not None:
            outcome = "FAILED" if issubclass(err[0], test.failureException) else "ERROR"
            self.outcomes[self.ids[id(test)]] = outcome


def _install_child_audit_hook(allowed_roots: list[Path]) -> dict[str, bool]:
    roots = [root.resolve() for root in allowed_roots]

    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event in BLOCKED_NETWORK_EVENTS:
            raise RuntimeError("reference_network_denied")
        if event in BLOCKED_PROCESS_EVENTS:
            raise RuntimeError("reference_process_denied")
        if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            candidate = Path(os.fsdecode(args[0]))
            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate
            resolved = candidate.resolve(strict=False)
            if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
                raise RuntimeError("reference_file_access_denied")

    sys.addaudithook(audit)
    controls: dict[str, bool] = {}
    try:
        socket.getaddrinfo("localhost", 0)
    except RuntimeError as error:
        controls["network_denied"] = str(error) == "reference_network_denied"
    else:
        controls["network_denied"] = False
    try:
        subprocess.run(["true"], check=False)
    except RuntimeError as error:
        controls["subprocess_denied"] = str(error) == "reference_process_denied"
    else:
        controls["subprocess_denied"] = False
    try:
        Path("/etc/passwd").read_bytes()
    except RuntimeError as error:
        controls["outside_read_denied"] = str(error) == "reference_file_access_denied"
    else:
        controls["outside_read_denied"] = False
    require(all(controls.values()), "child_isolation_control_failed")
    return controls


def validate_execution(result: dict[str, Any], expected_ids: list[str]) -> None:
    validate_ids(expected_ids)
    require(result.get("schema_version") == SCHEMA_VERSION, "execution_schema_mismatch")
    require(result.get("status") == "PASSED", "reference_execution_failed")
    require(result.get("python_isolated") is True and result.get("no_user_site") is True, "python_not_isolated")
    require(result.get("cwd_empty") is True, "child_cwd_not_empty")
    require(result.get("third_party_paths_removed") is True, "child_third_party_paths_present")
    require(result.get("ids_sha256") == IDS_SHA256, "execution_ids_digest_mismatch")
    cases = result.get("cases", [])
    observed_ids = [case.get("test_id") for case in cases]
    require(sorted(observed_ids) == expected_ids, "execution_case_set_mismatch")
    require(len(observed_ids) == len(set(observed_ids)) == 92, "execution_case_identity_invalid")
    require(all(case.get("outcome") == "PASSED" for case in cases), "execution_non_pass_outcome")
    require(all(case.get("body_executed") is True for case in cases), "execution_body_not_entered")
    require(result.get("tests_run") == 92, "execution_run_count_mismatch")
    require(result.get("bodies_started") == 92, "execution_body_count_mismatch")
    require(result.get("passed") == 92, "execution_pass_count_mismatch")
    for field in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes"):
        require(result.get(field) == 0, f"execution_nonzero:{field}")
    controls = result.get("controls", {})
    require(
        controls == {"network_denied": True, "outside_read_denied": True, "subprocess_denied": True},
        "execution_controls_failed",
    )
    require(result.get("module_origins") == REQUIRED_MODULES, "reference_module_origins_changed")


def run_child(project: Path, spec_path: Path, output: Path) -> int:
    require(sys.flags.isolated == 1 and sys.flags.no_user_site == 1, "isolated_python_required")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    expected_ids = validate_ids(spec.get("expected_ids", []))
    manifest = spec.get("manifest", {})
    require(isinstance(manifest, dict) and len(manifest) == 24, "child_manifest_invalid")
    project = project.resolve()
    source_root = (project / "src").resolve()
    scratch = output.parent.resolve()
    cwd_empty = not any(Path.cwd().iterdir())

    def is_third_party_path(item: str) -> bool:
        return any(part.lower() in {"site-packages", "dist-packages"} for part in Path(item or ".").parts)

    original_paths = list(sys.path)
    sys.path[:] = [item for item in original_paths if not is_third_party_path(item)]
    third_party_paths_removed = all(not is_third_party_path(item) for item in sys.path)
    sys.path.insert(0, str(project))
    sys.path.insert(0, str(source_root))
    controls = _install_child_audit_hook(
        [project, scratch, Path(sys.base_prefix), Path(sys.exec_prefix), Path(__file__).resolve().parent]
    )

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    module_paths: dict[str, str] = {}
    for index, test_path in enumerate(EXPECTED_TESTS):
        module_name = f"baseline92_reference_{index}_{Path(test_path).stem}"
        path = project / test_path
        module_spec = importlib.util.spec_from_file_location(module_name, path)
        require(module_spec is not None and module_spec.loader is not None, f"test_module_spec_failed:{test_path}")
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)
        module_paths[module_name] = test_path
        suite.addTests(loader.loadTestsFromModule(module))
    require(not loader.errors, "unittest_loader_errors")

    tests = _flatten_suite(suite)
    id_map: dict[int, str] = {}
    for test in tests:
        module_name = type(test).__module__
        require(module_name in module_paths, "test_loaded_from_unexpected_module")
        test_id = f"{module_paths[module_name]}::{type(test).__name__}::{test._testMethodName}"
        id_map[id(test)] = test_id
    require(validate_ids(id_map.values()) == expected_ids, "collected_ids_do_not_match_inventory")

    bodies_started: set[str] = set()
    for test in tests:
        method_name = test._testMethodName
        test_class = type(test)
        original = getattr(test_class, method_name)
        test_id = id_map[id(test)]

        def wrapped(instance: unittest.TestCase, *args: Any, _original: Callable[..., Any] = original,
                    _test_id: str = test_id, **kwargs: Any) -> Any:
            bodies_started.add(_test_id)
            return _original(instance, *args, **kwargs)

        setattr(test_class, method_name, wrapped)

    module_origins: dict[str, str] = {}
    for module_name, expected_path in REQUIRED_MODULES.items():
        module = importlib.import_module(module_name)
        origin = Path(module.__file__).resolve()
        require(origin.is_relative_to(project), f"reference_module_outside_tree:{module_name}")
        relative = origin.relative_to(project).as_posix()
        require(relative == expected_path, f"reference_module_origin_mismatch:{module_name}")
        require(sha256_bytes(origin.read_bytes()) == manifest[relative], f"reference_module_digest_mismatch:{module_name}")
        module_origins[module_name] = relative

    result = RecordingResult(id_map)
    unittest.TestSuite(tests).run(result)
    cases = [
        {
            "body_executed": test_id in bodies_started,
            "outcome": result.outcomes.get(test_id, "NOT_RECORDED"),
            "test_id": test_id,
        }
        for test_id in expected_ids
    ]
    execution = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASSED" if result.wasSuccessful() else "FAILED",
        "python": sys.version.split()[0],
        "python_isolated": True,
        "no_user_site": True,
        "cwd_empty": cwd_empty,
        "third_party_paths_removed": third_party_paths_removed,
        "ids_sha256": IDS_SHA256,
        "tests_run": result.testsRun,
        "bodies_started": len(bodies_started),
        "passed": sum(case["outcome"] == "PASSED" for case in cases),
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses),
        "controls": controls,
        "module_origins": dict(sorted(module_origins.items())),
        "cases": cases,
    }
    validate_execution(execution, expected_ids)
    with output.open("xb") as stream:
        stream.write(canonical(execution))
    return 0


def _run_child_process(project: Path, scratch: Path, expected_ids: list[str], manifest: dict[str, str]) -> dict[str, Any]:
    spec = scratch / "expected.json"
    output = scratch / "result.json"
    cwd = scratch / "empty-cwd"
    temp_root = scratch / "tmp"
    cwd.mkdir(parents=True)
    temp_root.mkdir()
    spec.write_bytes(canonical({"expected_ids": expected_ids, "manifest": manifest}))
    env = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        "TMPDIR": str(temp_root),
    }
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(Path(__file__).resolve()),
            "--child-project",
            str(project),
            "--child-spec",
            str(spec),
            "--child-output",
            str(output),
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    require(completed.returncode == 0, f"reference_child_failed:{completed.returncode}:{completed.stderr[-160:]}")
    result = json.loads(output.read_text(encoding="utf-8"))
    validate_execution(result, expected_ids)
    return result


def _expect_rejection(label: str, action: Callable[[], None], passed: list[str]) -> None:
    try:
        action()
    except ReferenceError:
        passed.append(label)
    else:
        raise ReferenceError(f"negative_control_false_positive:{label}")


def exercise_negative_controls(
    attestation: dict[str, Any], expected_ids: list[str], execution: dict[str, Any]
) -> list[str]:
    passed: list[str] = []

    for label, mutate in (
        ("wrong_generator_sha", lambda item: item["source"]["generator"].update(sha256="0" * 64)),
        ("wrong_payload_sha", lambda item: item["source"]["payload"].update(sha256="0" * 64)),
        ("false_current_engine_certification", lambda item: item["claims"].update(current_engine_baseline_functional_certified=True)),
    ):
        invalid = copy.deepcopy(attestation)
        mutate(invalid)
        _expect_rejection(label, lambda invalid=invalid: validate_attestation(invalid), passed)

    _expect_rejection("missing_test_id", lambda: validate_ids(expected_ids[:-1]), passed)
    duplicated = expected_ids[:-1] + [expected_ids[0]]
    _expect_rejection("duplicate_test_id", lambda: validate_ids(duplicated), passed)
    replaced = expected_ids[:-1] + ["tests/test_verificacao.py::TestRoteador::test_fake_same_count"]
    _expect_rejection("replaced_test_id_same_count", lambda: validate_ids(replaced), passed)

    for label, mutate in (
        ("missing_execution_case", lambda item: item["cases"].pop()),
        ("forged_pass_count", lambda item: item.update(passed=91)),
        ("body_not_executed", lambda item: item["cases"][0].update(body_executed=False)),
        ("skipped_test", lambda item: item["cases"][0].update(outcome="SKIPPED")),
    ):
        invalid_execution = copy.deepcopy(execution)
        mutate(invalid_execution)
        _expect_rejection(
            label,
            lambda invalid_execution=invalid_execution: validate_execution(invalid_execution, expected_ids),
            passed,
        )

    divergent = copy.deepcopy(execution)
    divergent["python"] = "0.0.0"
    _expect_rejection(
        "replay_divergence",
        lambda: require(canonical(execution) == canonical(divergent), "reference_replay_diverged"),
        passed,
    )
    return passed


def validate_final_report(report: dict[str, Any], expected_ids: list[str]) -> None:
    require(report.get("schema_version") == SCHEMA_VERSION, "report_schema_mismatch")
    require(report.get("claim") == "ORIGINAL_STANDALONE_REFERENCE_ONLY", "report_claim_mismatch")
    require(
        report.get("correlation_id") == "ocr-baseline92-reference-20261020-f487837f",
        "report_correlation_id_mismatch",
    )
    require(report.get("status") == FINAL_STATUS, "report_status_mismatch")
    require(
        report.get("original_v1_0_generator_and_payload_bytes_verified") is True,
        "report_original_generator_payload_unverified",
    )
    require(
        report.get("original_archive_bytes_reverified_in_this_run") is False,
        "report_false_original_archive_reverification",
    )
    require(report.get("reference_standalone_functional_certified") is True, "reference_not_certified")
    require(report.get("current_engine_baseline_functional_certified") is False, "report_false_current_certification")
    require(report.get("current_engine_status") == CURRENT_ENGINE_STATUS, "report_current_status_changed")
    require(report.get("semantic_equivalence_to_current_engine") == "NOT_PROVEN", "report_false_equivalence")
    require(report.get("consumer_sha") == CONSUMER_SHA, "report_consumer_sha_mismatch")
    require(
        report.get("compatibility_audit_sha") == COMPATIBILITY_AUDIT_SHA,
        "report_compatibility_audit_sha_mismatch",
    )
    require(report.get("reference") == {
        "archive_sha256": ORIGINAL_ARCHIVE_SHA256,
        "generator_sha256": GENERATOR_SHA256,
        "manifest_files": 24,
        "payload_sha256": PAYLOAD_SHA256,
        "source_commit": PRIVATE_SOURCE_COMMIT,
        "source_path": PRIVATE_SOURCE_PATH,
        "source_repository": PRIVATE_SOURCE_REPOSITORY,
        "version": "1.0.0",
    }, "report_reference_identity_mismatch")
    require(report.get("inventory") == {
        "expected_cases": 92,
        "ids_sha256": IDS_SHA256,
        "sha256": INVENTORY_SHA256,
    }, "report_inventory_identity_mismatch")
    require(report.get("attestation_sha256") == ATTESTATION_SHA256, "report_attestation_identity_mismatch")
    require(
        report.get("environment", {}).get("network_control")
        == "PYTHON_AUDIT_HOOK_DENIED_NETWORK_SUBPROCESS_AND_OUTSIDE_READ_NOT_OS_AIRGAP",
        "report_environment_claim_mismatch",
    )
    require(
        report.get("idempotency_scope")
        == "REFERENCE_SEQUENTIAL_MEMORY_AND_JSONL_REOPEN_ONLY_NOT_CONCURRENT_OR_DISTRIBUTED",
        "report_idempotency_scope_mismatch",
    )
    require(report.get("production_touched") is False, "report_false_production_claim")
    require(report.get("pin_changed") is False, "report_false_pin_claim")
    require(report.get("legacy_modules_integrated") is False, "report_false_integration_claim")
    summary = report.get("execution_summary", {})
    require(summary == {
        "bodies_executed_per_run": 92,
        "bodies_passed_per_run": 92,
        "cases_per_run": 92,
        "replays": 2,
        "total_body_invocations": 184,
    }, "report_execution_summary_mismatch")
    executions = report.get("executions", {})
    require(set(executions) == {"a", "b"}, "report_execution_set_mismatch")
    validate_execution(executions["a"], expected_ids)
    validate_execution(executions["b"], expected_ids)
    require(canonical(executions["a"]) == canonical(executions["b"]), "report_replay_not_identical")
    require(report.get("replay") == {
        "byte_identical": True,
        "independent_processes": 2,
        "independent_trees": 2,
    }, "report_replay_claim_mismatch")
    controls = report.get("negative_controls_passed", [])
    require(
        len(controls) == len(set(controls)) == 11 and set(controls) == NEGATIVE_CONTROL_NAMES,
        "report_negative_controls_incomplete",
    )


def build_reference_report(generator: Path, attestation_path: Path, inventory_path: Path) -> dict[str, Any]:
    attestation, attestation_sha = load_attestation(attestation_path)
    _, expected_ids, inventory_sha = load_inventory(inventory_path)
    reference = parse_reference(generator, attestation)
    require(_ids_from_sources(reference.files) == expected_ids, "reference_ids_do_not_match_inventory")

    with tempfile.TemporaryDirectory(prefix="ocr-baseline92-reference-") as temporary:
        root = Path(temporary)
        executions: dict[str, dict[str, Any]] = {}
        for label in ("a", "b"):
            project = extract_reference(reference, root / f"tree-{label}")
            executions[label] = _run_child_process(
                project, root / f"scratch-{label}", expected_ids, reference.manifest
            )
    require(canonical(executions["a"]) == canonical(executions["b"]), "reference_replay_diverged")
    negative_controls = exercise_negative_controls(attestation, expected_ids, executions["a"])

    report = {
        "schema_version": SCHEMA_VERSION,
        "claim": "ORIGINAL_STANDALONE_REFERENCE_ONLY",
        "correlation_id": attestation["correlation_id"],
        "audit_sha": os.environ.get("GITHUB_SHA", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "consumer_sha": CONSUMER_SHA,
        "compatibility_audit_sha": COMPATIBILITY_AUDIT_SHA,
        "reference": {
            "archive_sha256": ORIGINAL_ARCHIVE_SHA256,
            "generator_sha256": GENERATOR_SHA256,
            "manifest_files": 24,
            "payload_sha256": PAYLOAD_SHA256,
            "source_commit": PRIVATE_SOURCE_COMMIT,
            "source_path": PRIVATE_SOURCE_PATH,
            "source_repository": PRIVATE_SOURCE_REPOSITORY,
            "version": reference.version,
        },
        "inventory": {
            "ids_sha256": IDS_SHA256,
            "sha256": inventory_sha,
            "expected_cases": 92,
        },
        "attestation_sha256": attestation_sha,
        "environment": {
            "network_control": "PYTHON_AUDIT_HOOK_DENIED_NETWORK_SUBPROCESS_AND_OUTSIDE_READ_NOT_OS_AIRGAP",
            "python": sys.version.split()[0],
        },
        "executions": executions,
        "execution_summary": {
            "cases_per_run": 92,
            "bodies_executed_per_run": 92,
            "bodies_passed_per_run": 92,
            "replays": 2,
            "total_body_invocations": 184,
        },
        "replay": {
            "independent_processes": 2,
            "independent_trees": 2,
            "byte_identical": True,
        },
        "negative_controls_passed": negative_controls,
        "original_v1_0_generator_and_payload_bytes_verified": True,
        "original_archive_bytes_reverified_in_this_run": False,
        "reference_standalone_functional_certified": True,
        "current_engine_baseline_functional_certified": False,
        "current_engine_status": CURRENT_ENGINE_STATUS,
        "semantic_equivalence_to_current_engine": "NOT_PROVEN",
        "idempotency_scope": "REFERENCE_SEQUENTIAL_MEMORY_AND_JSONL_REOPEN_ONLY_NOT_CONCURRENT_OR_DISTRIBUTED",
        "production_touched": False,
        "pin_changed": False,
        "legacy_modules_integrated": False,
        "status": FINAL_STATUS,
    }
    validate_final_report(report, expected_ids)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generator", type=Path)
    parser.add_argument("--attestation", type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child-project", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--child-spec", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--child-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    child_values = (args.child_project, args.child_spec, args.child_output)
    if any(value is not None for value in child_values):
        require(all(value is not None for value in child_values), "incomplete_child_arguments")
        return run_child(args.child_project, args.child_spec, args.child_output)

    require(all(value is not None for value in (args.generator, args.attestation, args.inventory, args.output)),
            "generator_attestation_inventory_and_output_required")
    report = build_reference_report(args.generator, args.attestation, args.inventory)
    with args.output.open("xb") as stream:
        stream.write(canonical(report))
    print(json.dumps({
        "current_engine_baseline_functional_certified": False,
        "reference_standalone_functional_certified": True,
        "status": report["status"],
        "tests_per_run": 92,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"BASELINE92_REFERENCE_ERROR:{type(error).__name__}:{str(error)[:240]}", file=sys.stderr)
        raise SystemExit(3)
