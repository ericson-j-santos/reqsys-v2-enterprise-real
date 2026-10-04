#!/usr/bin/env python3
"""Bounded portable DEV candidate/activation controller; no legacy mutations."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request

try:
    from scripts import self_hosted_dev_maintenance as maintenance
    from scripts import reqsys_self_hosted_dev_publish as publisher
except ModuleNotFoundError:
    import self_hosted_dev_maintenance as maintenance
    import reqsys_self_hosted_dev_publish as publisher

Error = maintenance.PortableRuntimeError
HOST, PROJECT, INSTANCE = maintenance.HOST, maintenance.PROJECT, maintenance.INSTANCE
SOURCE_PROJECT = "wt-pc24x7-piloto"
NETWORK = PROJECT + "_outbound"
TARGET = "http://caddy:80"
IMAGE = "cloudflare/cloudflared:latest"
NAMES = ("reqsys-dev-selfhosted-tunnel-primary", "reqsys-dev-selfhosted-tunnel-secondary")
PAGES_ORIGIN = "https://ericson-j-santos.github.io"
REDIRECT = PAGES_ORIGIN + "/reqsys-v2-enterprise-real/dev/auth/callback.html"
DIGEST = re.compile(r"[0-9a-f]{64}")
IMAGE_DIGEST = re.compile(r"cloudflare/cloudflared@sha256:[0-9a-f]{64}")
URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
MAX_RESPONSE = 262144
RESTORE_FLAGS = ("archive_validated", "content_digests_match", "independent_readback",
                 "migration_committed", "sequences_verified", "schema_inventory_verified",
                 "runtime_keys_preserved")
FREEZE_FLAGS = ("source_writes_frozen", "consistent_backup_verified",
                "supervisor_lease_verified", "rollback_protected")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def integrity(value):
    return digest({key: item for key, item in value.items()
                   if key != "proof_integrity_sha256"})


def _bound(proof, sha, contract, sha_field="target_sha"):
    if not isinstance(proof, dict) or any(proof.get(key) != value for key, value in {
        "schema_version": "1", "contract": contract, "host": HOST,
        "project": PROJECT, "instance": INSTANCE, sha_field: sha,
    }.items()):
        raise Error("portable_cutover_proof_binding_invalid")
    if not maintenance.SHA_RE.fullmatch(sha):
        raise Error("portable_cutover_sha_invalid")
    if not DIGEST.fullmatch(str(proof.get("proof_integrity_sha256") or "")):
        raise Error("portable_cutover_proof_integrity_missing")
    if proof["proof_integrity_sha256"] != integrity(proof):
        raise Error("portable_cutover_proof_integrity_invalid")


def _time(value, now, maximum=None):
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if moment.tzinfo is None:
            raise ValueError
        age = (now - moment).total_seconds()
        if age < 0 or (maximum is not None and age > maximum):
            raise ValueError
    except (TypeError, ValueError):
        raise Error("portable_cutover_proof_time_invalid") from None


def _identity(value):
    if (not isinstance(value, dict) or value.get("database") != "reqsys"
            or not DIGEST.fullmatch(str(value.get("container_id") or ""))
            or not re.fullmatch(r"[0-9]{1,24}", str(value.get("postgres_system_identifier") or ""))):
        raise Error("portable_cutover_database_identity_invalid")


def validate_restore(proof, sha, now, fresh=True):
    _bound(proof, sha, "reqsys-current-postgres-restore")
    if proof.get("status") != "verified" or proof.get("source_engine") != "postgresql":
        raise Error("portable_cutover_authoritative_postgres_required")
    if proof.get("source_project") != SOURCE_PROJECT:
        raise Error("portable_cutover_source_project_invalid")
    if any(proof.get(flag) is not True for flag in RESTORE_FLAGS):
        raise Error("portable_cutover_restore_not_verified")
    if not DIGEST.fullmatch(str(proof.get("source_sha256") or "")):
        raise Error("portable_cutover_backup_digest_invalid")
    counts, rows = proof.get("table_counts"), proof.get("source_rows")
    if (type(rows) is not int or rows <= 0 or type(proof.get("copied_rows")) is not int
            or proof.get("copied_rows") != rows or not isinstance(counts, dict) or not counts
            or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", key)
                   or type(value) is not int or value < 0 for key, value in counts.items())
            or sum(counts.values()) != rows):
        raise Error("portable_cutover_restore_counts_invalid")
    _identity(proof.get("database_identity"))
    original = proof.get("backup_source_identity")
    if (not isinstance(original, dict) or original.get("database") != "reqsys"
            or original.get("role") != "reqsys_app"
            or any(not DIGEST.fullmatch(str(original.get(key) or ""))
                   for key in ("api_container_id", "database_container_id"))
            or not re.fullmatch(r"[0-9]{1,24}", str(original.get("postgres_system_identifier") or ""))):
        raise Error("portable_cutover_source_identity_invalid")
    _time(proof.get("verified_at"), now, 3600 if fresh else None)
    return proof


def validate_auth(proof, restore, config, sha, now, fresh=True):
    _bound(proof, sha, "reqsys-self-hosted-dev-azure-auth", "source_sha")
    if (proof.get("authenticated_flow_verified") is not True
            or proof.get("verification_scope") != "backend_azure_session"
            or proof.get("azure_login_status") != 200 or proof.get("api_session_status") != 200
            or proof.get("demo_login_enabled") is not False
            or proof.get("ui_interactive_callback_verified") is not False
            or proof.get("restore_proof_sha256") != digest(restore)
            or proof.get("auth_config_sha256") != digest(config)
            or any(proof.get(key) != value for key, value in config.items())):
        raise Error("portable_cutover_real_auth_proof_invalid")
    for flag in ("anonymous_session_rejected", "invalid_azure_signature_rejected"):
        if proof.get(flag) is not True:
            raise Error("portable_cutover_auth_negative_control_failed")
    _time(proof.get("verified_at"), now, 3600 if fresh else None)
    return proof


def validate_freeze(proof, restore, auth, sha, now):
    _bound(proof, sha, "reqsys-dev-authoritative-source-freeze")
    if (proof.get("status") != "verified"
            or any(proof.get(flag) is not True for flag in FREEZE_FLAGS)
            or proof.get("source_project") != SOURCE_PROJECT
            or proof.get("source_api_container_id") != restore["backup_source_identity"]["api_container_id"]
            or proof.get("source_sha256") != restore["source_sha256"]
            or proof.get("restore_proof_sha256") != digest(restore)
            or proof.get("auth_proof_sha256") != digest(auth)):
        raise Error("portable_cutover_current_source_not_frozen")
    _time(proof.get("verified_at"), now, 300)
    _time(proof.get("final_backup_verified_at"), now, 300)
    return proof


def validate_receipt(receipt, restore, auth, config, sha, now):
    _bound(receipt, sha, "reqsys-dev-public-cutover-activation", "source_sha")
    if (receipt.get("status") != "verified"
            or receipt.get("restore_proof_sha256") != digest(restore)
            or receipt.get("auth_proof_sha256") != digest(auth)
            or receipt.get("auth_config_sha256") != digest(config)
            or receipt.get("database_identity") != restore["database_identity"]
            or not DIGEST.fullmatch(str(receipt.get("source_freeze_proof_sha256") or ""))
            or any(receipt.get(key) is not True for key in (
                "candidate_public_ingress_verified", "source_writes_frozen",
                "runtime_keys_preserved", "backend_authenticated"))
            or receipt.get("ui_interactive_callback_verified") is not False):
        raise Error("portable_cutover_activation_receipt_invalid")
    _time(receipt.get("activated_at"), now)
    return receipt


def _locator():
    try:
        from scripts import pc24x7_dev_locator_publisher as locator
    except ModuleNotFoundError:
        import pc24x7_dev_locator_publisher as locator
    return locator


class Controller:
    def __init__(self, expected_sha, private=None):
        if not maintenance.SHA_RE.fullmatch(expected_sha):
            raise Error("portable_cutover_sha_invalid")
        maintenance._require_host()
        self.sha = expected_sha
        self.root = Path(os.environ["LOCALAPPDATA"]) / "ReqSys" / "SelfHostedDev"
        self.marker = maintenance.marker_path()
        self.private = private or publisher.WindowsPrivateFiles()
        self.private.check(self.root)
        self.deadline = time.monotonic() + 300

    def read_private(self, name):
        if name not in ("restore-proof.json", "auth-proof.json",
                        "source-freeze-proof.json", "activation-proof.json"):
            raise Error("portable_cutover_proof_path_not_allowed")
        path = self.root / name
        try:
            self.private.check(path)
            with path.open("rb") as stream:
                raw = stream.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise Error("portable_cutover_proof_too_large")
            result = maintenance._load_json(raw)
            if not isinstance(result, dict):
                raise Error("portable_cutover_proof_not_object")
            return result
        except Error:
            raise
        except (OSError, ValueError, publisher.PublishError):
            raise Error("portable_cutover_private_proof_unavailable") from None

    def docker(self, argv, timeout=30):
        # Only internal fixed templates call this method; no command CLI/input.
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Error("portable_cutover_deadline_exceeded")
        try:
            result = subprocess.run(["docker", *argv], capture_output=True, text=True,
                                    encoding="utf-8", errors="strict", shell=False,
                                    check=False, timeout=min(timeout, remaining))
        except (OSError, UnicodeError, subprocess.TimeoutExpired):
            raise Error("portable_cutover_docker_failed") from None
        if result.returncode or len(result.stdout) + len(result.stderr) > 1048576:
            raise Error("portable_cutover_docker_failed")
        # cloudflared emits its candidate URL on stderr, never echo raw logs.
        return ((result.stdout + "\n" + result.stderr) if argv[0] == "logs"
                else result.stdout).strip()

    def inspect(self, name, missing=False):
        allowed = {f"{PROJECT}-{service}-1" for service in maintenance.SERVICES} | set(NAMES)
        if name not in allowed and not DIGEST.fullmatch(name):
            raise Error("portable_cutover_container_not_allowed")
        if missing and name in NAMES:
            found = self.docker(["container", "ls", "--all", "--filter",
                                 "name=^/" + name + "$", "--format", "{{.Names}}"])
            if not found:
                return None
            if found != name:
                raise Error("portable_cutover_candidate_lookup_invalid")
        result = maintenance._load_json(self.docker(["inspect", name]).encode("utf-8"))
        if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
            raise Error("portable_cutover_inspection_invalid")
        return result[0]

    def owned_service(self, service, start=False):
        name = f"{PROJECT}-{service}-1"
        item = self.inspect(name)
        labels, state = item.get("Config", {}).get("Labels") or {}, item.get("State") or {}
        if (item.get("Name") != "/" + name or not DIGEST.fullmatch(str(item.get("Id") or ""))
                or labels.get("com.docker.compose.project") != PROJECT
                or labels.get("com.docker.compose.service") != service
                or labels.get("io.reqsys.selfhost.instance") != INSTANCE
                or state.get("Paused") or state.get("Restarting") or state.get("Dead")):
            raise Error("portable_cutover_service_ownership_invalid")
        if state.get("Running") is not True:
            if not start:
                raise Error("portable_cutover_service_not_running")
            self.docker(["start", name], timeout=30)
        return item

    def identity(self):
        item = self.owned_service("db")
        value = self.docker([
            "exec", f"{PROJECT}-db-1", "psql", "--no-psqlrc", "--quiet",
            "--tuples-only", "--no-align", "--set=ON_ERROR_STOP=1",
            "--username=reqsys_owner", "--dbname=reqsys", "--command",
            "SELECT system_identifier FROM pg_control_system();",
        ])
        identity = {"container_id": item["Id"], "postgres_system_identifier": value, "database": "reqsys"}
        _identity(identity)
        return identity

    def request(self, base, path, *, cors=False):
        if base != maintenance.GATEWAY and not URL.fullmatch(base):
            raise Error("portable_cutover_url_not_allowed")
        allowed = {*maintenance.REQUIRED_ENDPOINTS, "/task-console", "/@vite/client", "/api/v1/auth/config"}
        if path not in allowed and not (cors and path == "/api/v1/auth/azure"):
            raise Error("portable_cutover_endpoint_not_allowed")
        headers = {"User-Agent": "ReqSysPortableDevController/1.0", "Accept": "*/*"}
        if cors:
            headers.update({"Origin": PAGES_ORIGIN, "Access-Control-Request-Method": "POST",
                            "Access-Control-Request-Headers": "content-type,x-correlation-id"})
        request = urllib.request.Request(base + path, headers=headers, method="OPTIONS" if cors else "GET")
        try:
            with maintenance._OPENER.open(request, timeout=10) as response:
                raw = response.read(MAX_RESPONSE + 1)
                if response.status != 200 or len(raw) > MAX_RESPONSE:
                    raise Error("portable_cutover_http_contract_failed")
                if cors:
                    if (response.headers.get("Access-Control-Allow-Origin") != PAGES_ORIGIN
                            or "POST" not in str(response.headers.get("Access-Control-Allow-Methods"))):
                        raise Error("portable_cutover_pages_cors_failed")
                    return True
                if path == "/task-console":
                    text = raw.decode("utf-8")
                    if ("/assets/" not in text or "/src/main.js" in text
                            or "text/html" not in str(response.headers.get("Content-Type")).lower()):
                        raise Error("portable_cutover_static_frontend_failed")
                    return True
                if path == "/@vite/client":
                    raise Error("portable_cutover_vite_exposed")
                result = maintenance._load_json(raw)
                if not isinstance(result, dict):
                    raise Error("portable_cutover_json_invalid")
                return result
        except urllib.error.HTTPError as exc:
            if path == "/@vite/client" and exc.code == 404:
                return True
            raise Error("portable_cutover_http_contract_failed") from None
        except (OSError, UnicodeError, ValueError, urllib.error.URLError):
            raise Error("portable_cutover_http_contract_failed") from None

    def local_config(self, base=maintenance.GATEWAY):
        payload = self.request(base, "/api/v1/auth/config")
        data = payload.get("data")
        if (payload.get("success") is not True or payload.get("errors") != []
                or not isinstance(data, dict) or data.get("azure_enabled") is not True
                or data.get("auth_status") != "ready" or data.get("demo_login_enabled") is not False
                or data.get("environment") != "desenvolvimento"
                or data.get("expected_redirect_uri") != REDIRECT
                or any(not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}",
                                       str(data.get(key) or "")) for key in ("azure_tenant_id", "azure_client_id"))):
            raise Error("portable_cutover_auth_config_invalid")
        return {key: data[key] for key in (
            "azure_tenant_id", "azure_client_id", "expected_redirect_uri", "demo_login_enabled")}

    def local_ready(self):
        for service in maintenance.SERVICES:
            self.owned_service(service)
            maintenance._inspect(service, self.deadline)
        for path in maintenance.REQUIRED_ENDPOINTS:
            data = maintenance._health_data(path, self.request(maintenance.GATEWAY, path))
            if path.endswith("/build-info") and data.get("build_sha") != self.sha:
                raise Error("portable_cutover_build_sha_mismatch")
        self.request(maintenance.GATEWAY, "/task-console")
        self.request(maintenance.GATEWAY, "/@vite/client")
        return {"local_runtime_contract_ready": True}

    def wait_local_ready(self):
        retryable = {"portable_cutover_service_not_running",
                     "portable_runtime_container_not_running",
                     "portable_runtime_container_unhealthy",
                     "portable_cutover_http_contract_failed"}
        end = min(self.deadline, time.monotonic() + 120)
        while True:
            try:
                return self.local_ready()
            except Error as exc:
                if exc.code not in retryable or time.monotonic() >= end:
                    raise
                time.sleep(2)

    def candidates(self, apply):
        network = maintenance._load_json(self.docker(["network", "inspect", NETWORK]).encode("utf-8"))[0]
        labels = network.get("Labels") or {}
        if (network.get("Name") != NETWORK or network.get("Internal") is not False
                or labels.get("com.docker.compose.project") != PROJECT
                or labels.get("com.docker.compose.network") != "outbound"):
            raise Error("portable_cutover_network_not_owned")
        caddy = self.owned_service("caddy")
        if NETWORK not in caddy.get("NetworkSettings", {}).get("Networks", {}):
            raise Error("portable_cutover_caddy_network_missing")
        urls = []
        for name in NAMES:
            item = self.inspect(name, missing=True)
            if item is None:
                if not apply:
                    raise Error("portable_cutover_candidate_missing")
                image = maintenance._load_json(self.docker(["image", "inspect", IMAGE]).encode("utf-8"))[0]
                pinned = next((value for value in image.get("RepoDigests", [])
                               if IMAGE_DIGEST.fullmatch(value)), None)
                if pinned is None:
                    raise Error("portable_cutover_official_image_digest_missing")
                self.docker([
                    "run", "-d", "--name", name, "--restart", "unless-stopped", "--network", NETWORK,
                    "--label", "com.docker.compose.project=" + PROJECT,
                    "--label", "io.reqsys.selfhost.instance=" + INSTANCE,
                    "--label", "io.reqsys.selfhost.source_sha=" + self.sha,
                    pinned, "tunnel", "--url", TARGET,
                ])
                item = self.inspect(name)
            cfg, state = item.get("Config") or {}, item.get("State") or {}
            labels = cfg.get("Labels") or {}
            args = item.get("Args") or []
            if (item.get("Name") != "/" + name or not DIGEST.fullmatch(str(item.get("Id") or ""))
                    or labels.get("com.docker.compose.project") != PROJECT
                    or labels.get("io.reqsys.selfhost.instance") != INSTANCE
                    or labels.get("io.reqsys.selfhost.source_sha") != self.sha
                    or not IMAGE_DIGEST.fullmatch(str(cfg.get("Image") or ""))
                    or args not in (["tunnel", "--url", TARGET], ["--no-autoupdate", "tunnel", "--url", TARGET])
                    or set(item.get("NetworkSettings", {}).get("Networks", {})) != {NETWORK}
                    or item.get("HostConfig", {}).get("RestartPolicy", {}).get("Name") != "unless-stopped"
                    or state.get("Paused") or state.get("Restarting") or state.get("Dead")):
                raise Error("portable_cutover_candidate_ownership_invalid")
            if state.get("Running") is not True:
                if not apply:
                    raise Error("portable_cutover_candidate_not_running")
                self.docker(["start", name])
            url = None
            for _ in range(12):
                logs = self.docker(["logs", "--tail", "120", name], timeout=10)
                matches = URL.findall(logs)
                if matches:
                    url = matches[-1]
                    break
                time.sleep(1)
            if url is None:
                raise Error("portable_cutover_candidate_url_missing")
            for path in maintenance.REQUIRED_ENDPOINTS:
                data = maintenance._health_data(path, self.request(url, path))
                if path.endswith("/build-info") and data.get("build_sha") != self.sha:
                    raise Error("portable_cutover_candidate_sha_mismatch")
            self.request(url, "/task-console")
            self.request(url, "/@vite/client")
            self.request(url, "/api/v1/auth/azure", cors=True)
            if self.local_config(url) != self.local_config():
                raise Error("portable_cutover_candidate_config_mismatch")
            urls.append(url)
        if len(set(urls)) != 2:
            raise Error("portable_cutover_distinct_candidates_required")
        return urls

    def proofs(self, fresh):
        now = datetime.now(timezone.utc)
        config = self.local_config()
        restore = validate_restore(self.read_private("restore-proof.json"), self.sha, now, fresh)
        auth = validate_auth(self.read_private("auth-proof.json"), restore, config, self.sha, now, fresh)
        return restore, auth, config

    def verify_db(self, restore, historical=False):
        current = self.identity()
        expected = restore["database_identity"]
        if (current["postgres_system_identifier"] != expected["postgres_system_identifier"]
                or (not historical and current["container_id"] != expected["container_id"])):
            raise Error("portable_cutover_current_database_mismatch")

    def prepare(self):
        restore, auth, config = self.proofs(True)
        self.local_ready()
        self.verify_db(restore)
        urls = self.candidates(True)
        return {"status": "candidates_verified", "source_sha": self.sha,
                "urls": urls, "public_ingress_verified": True,
                "locator_published": False, "usable": False}

    def sign_publish(self, urls, sign_only_output=None):
        locator = _locator()
        key, cfg = locator.ensure_identity()  # DPAPI existing pinned identity; never generates.
        envelope = locator.sign_payload(locator.build_payload(urls), key)
        if sign_only_output is not None:
            output = Path(sign_only_output)
            temporary = Path(os.environ.get("RUNNER_TEMP", ""))
            if (not temporary.is_absolute() or not output.is_absolute()
                    or not output.is_relative_to(temporary)
                    or output.name != "envelope.json"):
                raise Error("portable_cutover_relay_output_not_allowed")
            for parent in reversed(output.parents):
                if not maintenance._check_nonlink(parent, required=False, directory=True):
                    break
            locator.write_sign_only_envelope(output, envelope)
            return {"signed": True, "published": False, "relay_ready": True}
        if locator.publish_envelope(cfg["topic"], envelope) != 200:
            raise Error("portable_cutover_locator_publication_failed")
        request = urllib.request.Request(
            "https://ntfy.sh/" + cfg["topic"] + "/json?poll=1&since=5m",
            headers={"Accept": "application/x-ndjson"})
        try:
            with locator.open_no_redirect(request, timeout=15) as response:
                raw = response.read(1048577)
                if response.status != 200 or len(raw) > 1048576:
                    raise Error("portable_cutover_locator_readback_failed")
            exact = envelope.decode("utf-8")
            found = any(
                row.get("event") == "message" and row.get("title") == locator.LOCATOR_TITLE
                and row.get("message") == exact
                for row in (maintenance._load_json(line) for line in raw.splitlines() if line)
            )
            if not found:
                raise Error("portable_cutover_locator_readback_failed")
        except Error:
            raise
        except (OSError, UnicodeError, ValueError, urllib.error.URLError):
            raise Error("portable_cutover_locator_readback_failed") from None
        return {"signed": True, "published": True, "locator_readback_verified": True}

    def activate(self):
        restore, auth, config = self.proofs(True)
        self.local_ready()
        self.verify_db(restore)
        freeze = validate_freeze(self.read_private("source-freeze-proof.json"),
                                 restore, auth, self.sha, datetime.now(timezone.utc))
        original = self.inspect(freeze["source_api_container_id"])
        labels = original.get("Config", {}).get("Labels") or {}
        if (original.get("Id") != freeze["source_api_container_id"]
                or labels.get("com.docker.compose.project") != SOURCE_PROJECT
                or labels.get("com.docker.compose.service") != "api"
                or original.get("State", {}).get("Running") is not False):
            raise Error("portable_cutover_authoritative_api_not_frozen")
        urls = self.candidates(True)
        _locator().ensure_identity()
        self.private.check(self.marker.parent)
        receipt = {
            "schema_version": "1", "contract": "reqsys-dev-public-cutover-activation",
            "status": "verified", "host": HOST, "project": PROJECT, "instance": INSTANCE,
            "source_sha": self.sha, "restore_proof_sha256": digest(restore),
            "auth_proof_sha256": digest(auth), "auth_config_sha256": digest(config),
            "source_freeze_proof_sha256": digest(freeze),
            "database_identity": restore["database_identity"],
            "candidate_public_ingress_verified": True, "source_writes_frozen": True,
            "runtime_keys_preserved": True, "backend_authenticated": True,
            "ui_interactive_callback_verified": False,
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "locator_published": False,
        }
        receipt["proof_integrity_sha256"] = integrity(receipt)
        self.private.preserving(self.root / "activation-proof.json", canonical(receipt) + b"\n")
        marker = {"schema_version": "1.0.0", "host": HOST, "environment": "dev",
                  "project": PROJECT, "instance": INSTANCE, "source_sha": self.sha}
        # Receipt and all public/private evidence precede marker; marker precedes publish.
        self.private.preserving(self.marker, canonical(marker) + b"\n")
        publication = self.sign_publish(urls)  # failure leaves new marker bound; no fallback.
        return self.result(urls, publication, historical=False)

    def result(self, urls, publication, historical):
        return {"status": "dev_route_active" if publication.get("published") else "dev_route_signed",
                "runtime_provider": "self_hosted_dev", "host": HOST, "project": PROJECT,
                "instance": INSTANCE, "expected_sha": self.sha, "build_sha": self.sha,
                "maintenance_verified": True, "maintenance_read_only": False,
                "local_runtime_contract_ready": True, "public_ingress_verified": True,
                "authenticated_flow_verified": True, "authenticated_flow_rechecked": False,
                "authentication_evidence_historical": historical,
                "runtime_key_fidelity_rechecked": False,
                "ui_interactive_callback_verified": False, "usable": False,
                "urls": urls, "healthy_url_count": len(urls),
                "selected_url": urls[0], "legacy_runtime_touched": False,
                "production_touched": False, "secret_value_exposed": False, **publication}

    def maintain(self, marker, publish=True, apply=True, sign_only_output=None):
        if marker != {"schema_version": "1.0.0", "host": HOST, "environment": "dev",
                      "project": PROJECT, "instance": INSTANCE, "source_sha": self.sha}:
            raise Error("portable_cutover_marker_binding_invalid")
        self.private.check(self.marker.parent)
        self.private.check(self.marker)
        now = datetime.now(timezone.utc)
        restore = validate_restore(self.read_private("restore-proof.json"), self.sha, now, False)
        auth = self.read_private("auth-proof.json")
        # Validate private historical receipt before any restart; no live API needed yet.
        config = {key: auth.get(key) for key in ("azure_tenant_id", "azure_client_id",
                  "expected_redirect_uri", "demo_login_enabled")}
        validate_auth(auth, restore, config, self.sha, now, False)
        validate_receipt(self.read_private("activation-proof.json"), restore, auth, config,
                         self.sha, now)
        if apply:
            for service in maintenance.SERVICES:
                self.owned_service(service, start=True)
            self.wait_local_ready()
        else:
            self.local_ready()
        if self.local_config() != config:
            raise Error("portable_cutover_active_auth_config_changed")
        self.verify_db(restore, historical=True)  # no historic row/keyring byte equality.
        urls = self.candidates(apply)
        publication = self.sign_publish(urls, sign_only_output) if publish else {"published": False}
        return self.result(urls, publication, historical=True)


def control_if_active(expected_sha=None, *, apply=False, publish=False, sign_only_output=None):
    marker = maintenance.read_marker()
    if marker is None:
        return None
    if expected_sha is not None and expected_sha != marker["source_sha"]:
        raise Error("portable_cutover_expected_sha_mismatch")
    return Controller(marker["source_sha"]).maintain(
        marker, publish=publish, apply=apply, sign_only_output=sign_only_output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare-candidates", "activate"))
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    confirmations = {
        "prepare-candidates": "PREPARE-PC24X7-SELFHOSTED-DEV-CANDIDATES",
        "activate": "ACTIVATE-PC24X7-SELFHOSTED-DEV-PUBLIC-ROUTE",
    }
    try:
        if args.confirm != confirmations[args.phase]:
            raise Error("portable_cutover_confirmation_required")
        controller = Controller(args.expected_sha)
        verifier = publisher.Publisher(Path(__file__).resolve().parents[1],
                                        args.expected_sha, controller.private,
                                        "self-hosted-dev-candidate-control")
        verifier.validate_source()
        result = controller.prepare() if args.phase == "prepare-candidates" else controller.activate()
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "usable": False,
                          "runtime_provider": "self_hosted_dev", "legacy_runtime_touched": False,
                          "error": exc.code if isinstance(exc, (Error, publisher.PublishError))
                          else "portable_cutover_controller_failed"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
