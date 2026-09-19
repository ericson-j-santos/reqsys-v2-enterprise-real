#!/usr/bin/env python3
"""Supervisor PC24x7 do Codex/Ollama no Desktop ReqSys.

Escopo local/DEV:
- lê somente configuração Ollama allowlisted do perfil Windows;
- mantém Ollama :11434, gateway :8008 e backend :8000 em loopback;
- reinicia somente processos iniciados pela instância corrente do supervisor;
- executa smoke ReqSys -> ollama_gateway -> Ollama sem publicar no ReqSys;
- registra estado/evidência em LOCALAPPDATA;
- instala persistência Windows AtStartup; se a criação da tarefa for negada,
  registra fallback explícito AtLogon, sem tratar isso como headless 24x7.
"""
from __future__ import annotations

import argparse
import getpass
import json
import locale
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HOST = "DESKTOP-PDQK954"
SERVICE_NAME = "reqsys-codex-pc24x7-supervisor"
TASK_FOLDER = r"\Automation"
TASK_LEAF = "ReqSysCodexPC24x7Supervisor"
TASK_NAME = TASK_FOLDER + "\\" + TASK_LEAF
TASK_TRIGGER_BOOT = 8
TASK_ACTION_EXEC = 0
TASK_LOGON_S4U = 2
TASK_CREATE_OR_UPDATE = 6
TASK_RUNLEVEL_LUA = 0
TASK_INSTANCES_IGNORE_NEW = 2
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "ReqSysCodexPC24x7Supervisor"
DEFAULT_GATEWAY_PORT = 8008
DEFAULT_BACKEND_PORT = 8000
DEFAULT_OLLAMA_PORT = 11434
DEFAULT_WATCH_SECONDS = 15
DEFAULT_SMOKE_SECONDS = 900
STARTUP_TIMEOUT_SECONDS = 60
FALLBACK_TIMEOUT_SECONDS = 180
PROFILE_KEYS = (
    "CODEX_OLLAMA_MODEL",
    "CODEX_OLLAMA_GATEWAY_MODEL",
    "CODEX_OLLAMA_FALLBACK_MODEL",
    "CODEX_OLLAMA_BASE_URL",
)


class SupervisorError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_windows_desktop() -> str:
    if os.name != "nt":
        raise SupervisorError("Windows obrigatório")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise SupervisorError(f"host não autorizado: {host}")
    return host


def default_runtime_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise SupervisorError("LOCALAPPDATA não definido")
    return Path(local) / "ReqSys" / "CodexSupervisor"


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=True, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def windows_boot_epoch() -> int:
    if os.name != "nt":
        raise SupervisorError("boot epoch exige Windows")
    import ctypes

    ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    uptime = int(ctypes.windll.kernel32.GetTickCount64() // 1000)
    return int(time.time()) - uptime


def _winreg():
    if os.name != "nt":
        raise SupervisorError("registro Windows indisponível")
    import winreg
    return winreg


def read_profile() -> dict[str, str]:
    winreg = _winreg()
    values: dict[str, str] = {}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ) as key:
        for name in PROFILE_KEYS:
            try:
                value, _ = winreg.QueryValueEx(key, name)
            except FileNotFoundError as exc:
                raise SupervisorError(f"perfil Ollama incompleto: {name}") from exc
            text = str(value).strip()
            if not text:
                raise SupervisorError(f"perfil Ollama vazio: {name}")
            values[name] = text
    validate_profile(values)
    return values


def validate_profile(values: dict[str, str]) -> None:
    missing = [name for name in PROFILE_KEYS if not str(values.get(name) or "").strip()]
    if missing:
        raise SupervisorError("perfil Ollama incompleto: " + ", ".join(missing))
    base = values["CODEX_OLLAMA_BASE_URL"].rstrip("/")
    if base not in {"http://127.0.0.1:11434", "http://localhost:11434"}:
        raise SupervisorError("CODEX_OLLAMA_BASE_URL deve usar loopback :11434")
    if values["CODEX_OLLAMA_MODEL"] != values["CODEX_OLLAMA_GATEWAY_MODEL"]:
        raise SupervisorError("modelo direto e gateway devem ser idênticos")


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 5.0,
) -> tuple[int, dict[str, Any]]:
    data = None
    request_headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return int(response.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": raw[:300]}
        return int(exc.code), payload
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SupervisorError(f"HTTP indisponível em {url}: {exc}") from exc


def _port_open(port: int) -> bool:
    import socket as socket_module

    with socket_module.socket(socket_module.AF_INET, socket_module.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def probe_ollama() -> dict[str, Any] | None:
    try:
        code, payload = _request_json("http://127.0.0.1:11434/api/version", timeout=2)
    except SupervisorError:
        return None
    if code != 200 or not isinstance(payload, dict) or not payload.get("version"):
        return None
    return {"ok": True, "service": "ollama", "version": str(payload["version"])}


def probe_gateway() -> dict[str, Any] | None:
    try:
        code, payload = _request_json("http://127.0.0.1:8008/health", timeout=2)
    except SupervisorError:
        return None
    if code != 200 or payload.get("service") != "reqsys-ollama-local-gateway":
        return None
    return payload


def probe_backend() -> dict[str, Any] | None:
    try:
        code, payload = _request_json("http://127.0.0.1:8000/health", timeout=3)
    except SupervisorError:
        return None
    if code != 200:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or data.get("service") != "reqsys-api":
        return None
    return payload


def wait_probe(probe, timeout: float, process: subprocess.Popen[Any] | None = None) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = probe()
        if value is not None:
            return value
        if process is not None and process.poll() is not None:
            raise SupervisorError(f"processo terminou durante startup: exit={process.returncode}")
        time.sleep(0.5)
    raise SupervisorError("timeout aguardando health")


def _creationflags() -> int:
    if os.name != "nt":
        return 0
    return subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS


def _open_log(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a", encoding="utf-8", buffering=1)


def locate_ollama_executable() -> Path:
    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.extend(
            [
                Path(local) / "Programs" / "Ollama" / "ollama.exe",
                Path(local) / "Ollama" / "ollama.exe",
            ]
        )
    which = shutil.which("ollama")
    if which:
        candidates.append(Path(which))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SupervisorError("ollama.exe não encontrado")


def build_gateway_env(profile: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(profile)
    env.update(
        {
            "REQSYS_ENV": "dev",
            "REQSYS_AUTH_REQUIRED": "false",
            "REQSYS_OLLAMA_BASE_URL": profile["CODEX_OLLAMA_BASE_URL"],
            "REQSYS_OLLAMA_FALLBACK_MODEL": profile["CODEX_OLLAMA_FALLBACK_MODEL"],
            "REQSYS_OLLAMA_TIMEOUT_SECONDS": "60",
            "REQSYS_OLLAMA_FALLBACK_TIMEOUT_SECONDS": str(FALLBACK_TIMEOUT_SECONDS),
        }
    )
    return env


def build_backend_env(profile: dict[str, str], runtime_root: Path, source_sha: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(profile)
    db = runtime_root / "data" / "reqsys-codex-supervisor.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "APP_ENV": "development",
            "ENVIRONMENT": "development",
            "PUBLIC_ENVIRONMENT": "development",
            "ALLOW_DEMO_LOGIN": "true",
            "DATABASE_URL": f"sqlite:///{db.as_posix()}",
            "CODEX_OLLAMA_GATEWAY_URL": "http://127.0.0.1:8008",
            "CODEX_OLLAMA_GATEWAY_API_KEY": "",
            "CODEX_OLLAMA_GATEWAY_MODEL": profile["CODEX_OLLAMA_GATEWAY_MODEL"],
            "CODEX_OLLAMA_FALLBACK_MODEL": profile["CODEX_OLLAMA_FALLBACK_MODEL"],
            "CODEX_OLLAMA_FALLBACK_TIMEOUT_SECONDS": str(FALLBACK_TIMEOUT_SECONDS),
            "COFRE_API_URL": "",
            "COFRE_SERVICE_TOKEN": "",
            "GITHUB_SHA": source_sha,
        }
    )
    return env


class Supervisor:
    def __init__(self, metadata_path: Path) -> None:
        self.metadata_path = metadata_path
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.runtime_root = Path(self.metadata["runtime_root"])
        self.release_root = Path(self.metadata["release_root"])
        self.python = Path(self.metadata["python_executable"])
        self.source_sha = str(self.metadata["source_sha"])
        self.profile = read_profile()
        self.children: dict[str, subprocess.Popen[Any]] = {}
        self.log_handles: list[Any] = []
        self.restart_counts = {"ollama": 0, "gateway": 0, "backend": 0}
        self.last_smoke_at = 0.0

    def _spawn(self, name: str, command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen[Any]:
        log = _open_log(self.runtime_root / "logs" / f"{name}.log")
        self.log_handles.append(log)
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=_creationflags(),
        )
        self.children[name] = process
        self.restart_counts[name] += 1
        return process

    def _child_alive(self, name: str) -> bool:
        process = self.children.get(name)
        return process is not None and process.poll() is None

    def ensure_ollama(self) -> dict[str, Any]:
        health = probe_ollama()
        if health:
            return {"status": "healthy", "managed": self._child_alive("ollama"), "health": health}
        if _port_open(DEFAULT_OLLAMA_PORT):
            raise SupervisorError("porta 11434 ocupada sem health Ollama válido")
        executable = locate_ollama_executable()
        process = self._spawn("ollama", [str(executable), "serve"], executable.parent, os.environ.copy())
        health = wait_probe(probe_ollama, STARTUP_TIMEOUT_SECONDS, process)
        return {"status": "recovered", "managed": True, "pid": process.pid, "health": health}

    def ensure_gateway(self) -> dict[str, Any]:
        health = probe_gateway()
        if health:
            return {"status": "healthy", "managed": self._child_alive("gateway"), "health": health}
        process = self.children.get("gateway")
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=8)
        if _port_open(DEFAULT_GATEWAY_PORT):
            raise SupervisorError("porta 8008 ocupada sem health do gateway válido")
        gateway_src = self.release_root / "gateway_src"
        command = [
            str(self.python),
            "-m",
            "uvicorn",
            "reqsys_ollama_gateway.main:app",
            "--app-dir",
            str(gateway_src),
            "--host",
            "127.0.0.1",
            "--port",
            str(DEFAULT_GATEWAY_PORT),
            "--log-level",
            "warning",
        ]
        process = self._spawn("gateway", command, self.release_root, build_gateway_env(self.profile))
        health = wait_probe(probe_gateway, STARTUP_TIMEOUT_SECONDS, process)
        return {"status": "recovered", "managed": True, "pid": process.pid, "health": health}

    def ensure_backend(self) -> dict[str, Any]:
        health = probe_backend()
        if health:
            return {"status": "healthy", "managed": self._child_alive("backend"), "health": health}
        process = self.children.get("backend")
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=8)
        if _port_open(DEFAULT_BACKEND_PORT):
            raise SupervisorError("porta 8000 ocupada sem health do backend válido")
        backend = self.release_root / "backend"
        command = [
            str(self.python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            str(backend),
            "--host",
            "127.0.0.1",
            "--port",
            str(DEFAULT_BACKEND_PORT),
            "--log-level",
            "warning",
        ]
        process = self._spawn(
            "backend",
            command,
            backend,
            build_backend_env(self.profile, self.runtime_root, self.source_sha),
        )
        health = wait_probe(probe_backend, STARTUP_TIMEOUT_SECONDS, process)
        return {"status": "recovered", "managed": True, "pid": process.pid, "health": health}

    def smoke(self, correlation_id: str) -> dict[str, Any]:
        model = self.profile["CODEX_OLLAMA_GATEWAY_MODEL"]
        fallback = self.profile["CODEX_OLLAMA_FALLBACK_MODEL"]
        started = time.perf_counter()
        code, gateway = _request_json(
            "http://127.0.0.1:8008/v1/chat",
            method="POST",
            body={
                "model": model,
                "fallback_model": fallback,
                "task_type": "code",
                "prompt": "Responda somente com CODEX_SUPERVISOR_OK.",
                "contexto": "smoke pc24x7 local",
                "entrada": "health",
                "correlation_id": correlation_id,
                "source": "reqsys-codex-pc24x7-supervisor",
            },
            timeout=FALLBACK_TIMEOUT_SECONDS + 30,
        )
        if code != 200 or not str(gateway.get("response") or "").strip():
            raise SupervisorError(f"gateway smoke falhou: HTTP {code}")
        actual_model = str(gateway.get("model") or "")
        if actual_model not in {model, fallback}:
            raise SupervisorError("gateway smoke retornou modelo efetivo inesperado")

        code, login = _request_json(
            "http://127.0.0.1:8000/v1/auth/login",
            method="POST",
            body={"email": "codex-supervisor@example.com"},
            timeout=15,
        )
        if code != 200:
            raise SupervisorError(f"login smoke falhou: HTTP {code}")
        token = str(((login.get("data") or {}).get("access_token")) or "")
        if not token:
            raise SupervisorError("login smoke sem token")

        code, analyze = _request_json(
            "http://127.0.0.1:8000/v1/codex/analyze",
            method="POST",
            headers={"Authorization": f"Bearer {token}", "X-Correlation-Id": correlation_id},
            body={
                "provider": "ollama_gateway",
                "contexto": "smoke pc24x7 sem publicação",
                "entrada": "Responda somente com CODEX_REQSYS_OK.",
                "correlation_id": correlation_id,
                "publicar_no_reqsys": False,
            },
            timeout=FALLBACK_TIMEOUT_SECONDS + 30,
        )
        if code != 200:
            raise SupervisorError(f"ReqSys smoke falhou: HTTP {code}")
        data = analyze.get("data") or {}
        if data.get("provider") != "ollama_gateway" or not str(data.get("resultado") or "").strip():
            raise SupervisorError("ReqSys smoke sem resposta válida")
        if bool((data.get("reqsys_publicacao") or {}).get("publicado")):
            raise SupervisorError("smoke publicou indevidamente no ReqSys")

        self.last_smoke_at = time.time()
        return {
            "ok": True,
            "correlation_id": correlation_id,
            "requested_model": model,
            "actual_model": actual_model,
            "fallback_used": bool(gateway.get("fallback_used")),
            "provider": data.get("provider"),
            "published_to_reqsys": False,
            "wall_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    def cycle(self, *, force_smoke: bool = False) -> dict[str, Any]:
        observed = {
            "ollama": self.ensure_ollama(),
            "gateway": self.ensure_gateway(),
            "backend": self.ensure_backend(),
        }
        smoke = None
        now = time.time()
        smoke_interval = int(self.metadata.get("smoke_interval_seconds") or DEFAULT_SMOKE_SECONDS)
        if force_smoke or self.last_smoke_at == 0 or now - self.last_smoke_at >= smoke_interval:
            smoke = self.smoke(f"codex-supervisor-{int(now)}")
        payload = {
            "schema_version": "1",
            "service": SERVICE_NAME,
            "host": socket.gethostname(),
            "source_sha": self.source_sha,
            "generated_at": now_iso(),
            "profile": {
                "primary_model": self.profile["CODEX_OLLAMA_MODEL"],
                "fallback_model": self.profile["CODEX_OLLAMA_FALLBACK_MODEL"],
                "base_url": self.profile["CODEX_OLLAMA_BASE_URL"],
            },
            "components": observed,
            "restart_counts": dict(self.restart_counts),
            "supervisor_pid": os.getpid(),
            "smoke": smoke,
            "ok": True,
            "production_touched": False,
            "deploy_performed": False,
        }
        atomic_json(self.runtime_root / "state.json", payload)
        if smoke is not None:
            atomic_json(self.runtime_root / "last-smoke.json", smoke)
        return payload

    def _acquire_watch_lock(self):
        path = self.runtime_root / "supervisor.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+b")
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                handle.close()
                raise SupervisorError("outro supervisor já está ativo") from exc
        return handle

    def watch(self) -> int:
        interval = int(self.metadata.get("watch_interval_seconds") or DEFAULT_WATCH_SECONDS)
        lock_handle = self._acquire_watch_lock()
        while True:
            try:
                self.cycle()
            except Exception as exc:
                atomic_json(
                    self.runtime_root / "state.json",
                    {
                        "schema_version": "1",
                        "service": SERVICE_NAME,
                        "host": socket.gethostname(),
                        "source_sha": self.source_sha,
                        "generated_at": now_iso(),
                        "ok": False,
                        "error": str(exc)[:1000],
                        "error_type": type(exc).__name__,
                        "restart_counts": dict(self.restart_counts),
                        "production_touched": False,
                        "deploy_performed": False,
                    },
                )
            time.sleep(max(5, interval))


def current_user_id() -> str:
    return f"{socket.gethostname()}\\\\{getpass.getuser()}"


def register_task_com(*, python_executable: Path, launcher: Path) -> dict[str, Any]:
    require_windows_desktop()
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise SupervisorError("pywin32 indisponível no Python base") from exc

    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    try:
        folder = service.GetFolder(TASK_FOLDER)
    except Exception:
        root = service.GetFolder("\\")
        folder = root.CreateFolder(TASK_FOLDER.lstrip("\\"))

    definition = service.NewTask(0)
    definition.RegistrationInfo.Description = "ReqSys Codex/Ollama PC24x7 local DEV supervisor"
    definition.Settings.Enabled = True
    definition.Settings.StartWhenAvailable = True
    definition.Settings.DisallowStartIfOnBatteries = False
    definition.Settings.StopIfGoingOnBatteries = False
    definition.Settings.MultipleInstances = TASK_INSTANCES_IGNORE_NEW
    definition.Settings.ExecutionTimeLimit = "PT0S"

    trigger = definition.Triggers.Create(TASK_TRIGGER_BOOT)
    trigger.Enabled = True
    trigger.Delay = "PT20S"

    action = definition.Actions.Create(TASK_ACTION_EXEC)
    action.Path = str(python_executable)
    action.Arguments = f'"{launcher}"'
    action.WorkingDirectory = str(launcher.parent)

    principal = definition.Principal
    principal.UserId = current_user_id()
    principal.LogonType = TASK_LOGON_S4U
    principal.RunLevel = TASK_RUNLEVEL_LUA

    folder.RegisterTaskDefinition(
        TASK_LEAF,
        definition,
        TASK_CREATE_OR_UPDATE,
        principal.UserId,
        "",
        TASK_LOGON_S4U,
    )
    return {
        "ok": True,
        "task_name": TASK_NAME,
        "trigger": "AtStartup",
        "logon_type": "S4U",
        "password_used": False,
        "run_level": "limited",
    }


def _register_task_via_base_python(
    *,
    release_supervisor: Path,
    python_executable: Path,
    launcher: Path,
) -> subprocess.CompletedProcess[str]:
    base_python = Path(getattr(sys, "_base_executable", "") or sys.executable)
    return subprocess.run(
        [
            str(base_python),
            str(release_supervisor),
            "register-task-com",
            "--python-executable",
            str(python_executable),
            "--launcher",
            str(launcher),
        ],
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False) or "utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def _schtasks() -> Path:
    root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    target = root / "System32" / "schtasks.exe"
    if not target.is_file():
        raise SupervisorError("schtasks.exe não encontrado")
    return target


def _write_launcher(runtime_root: Path) -> Path:
    launcher = runtime_root / "run.py"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        "from pathlib import Path\n"
        "import json, runpy, sys\n"
        "metadata = Path(__file__).with_name('metadata.json')\n"
        "payload = json.loads(metadata.read_text(encoding='utf-8'))\n"
        "script = Path(payload['release_root']) / 'scripts' / 'codex_pc24x7_supervisor.py'\n"
        "sys.argv = [str(script), 'watch', '--metadata', str(metadata)]\n"
        "runpy.run_path(str(script), run_name='__main__')\n",
        encoding="utf-8",
    )
    return launcher


def _task_action(python: Path, launcher: Path) -> str:
    return f'"{python}" "{launcher}"'


def _run_schtasks(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_schtasks()), *args],
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False) or "utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def task_status() -> dict[str, Any]:
    if os.name != "nt":
        return {"exists": False, "trigger_at_startup": False}
    result = _run_schtasks(["/Query", "/TN", TASK_NAME, "/XML"])
    if result.returncode != 0:
        return {"exists": False, "trigger_at_startup": False, "returncode": result.returncode}
    try:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(result.stdout)
        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
        boot = root.find(".//t:BootTrigger", ns) is not None
        command = root.findtext(".//t:Exec/t:Command", default="", namespaces=ns)
        arguments = root.findtext(".//t:Exec/t:Arguments", default="", namespaces=ns)
        logon_type = root.findtext(".//t:Principal/t:LogonType", default="", namespaces=ns)
    except Exception as exc:
        return {
            "exists": True,
            "trigger_at_startup": False,
            "returncode": result.returncode,
            "parse_error": str(exc)[:300],
        }
    return {
        "exists": True,
        "trigger_at_startup": boot,
        "returncode": result.returncode,
        "task_name": TASK_NAME,
        "command": command,
        "arguments_present": bool(arguments.strip()),
        "logon_type": logon_type,
    }


def _install_run_key(action: str) -> None:
    winreg = _winreg()
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, action)


def _remove_run_key() -> None:
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_VALUE)
    except FileNotFoundError:
        return


def run_key_status() -> dict[str, Any]:
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE)
    except FileNotFoundError:
        return {"configured": False}
    return {"configured": bool(str(value).strip()), "value_name": RUN_VALUE}


def _copy_release(source_root: Path, release_root: Path) -> None:
    if release_root.exists():
        return
    temp = release_root.with_name(release_root.name + ".tmp")
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True, exist_ok=False)
    ignore = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "*.pyo", "*.db", "*.sqlite", "*.sqlite3")
    shutil.copytree(source_root / "backend", temp / "backend", ignore=ignore)
    shutil.copytree(
        source_root / "docs" / "ollama-local-gateway" / "bootstrap-files" / "src",
        temp / "gateway_src",
        ignore=ignore,
    )
    scripts = temp / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), scripts / Path(__file__).name)
    os.replace(temp, release_root)


def install(
    source_root: Path,
    *,
    source_sha: str,
    python_executable: Path,
    runtime_root: Path,
) -> dict[str, Any]:
    host = require_windows_desktop()
    profile = read_profile()
    if len(source_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in source_sha):
        raise SupervisorError("source_sha inválido")
    if not python_executable.is_file():
        raise SupervisorError("Python do backend não encontrado")
    for path in (
        source_root / "backend",
        source_root / "docs" / "ollama-local-gateway" / "bootstrap-files" / "src",
    ):
        if not path.is_dir():
            raise SupervisorError(f"fonte necessária ausente: {path}")

    release_root = runtime_root / "releases" / source_sha
    _copy_release(source_root, release_root)
    supervisor = release_root / "scripts" / Path(__file__).name
    metadata_file = runtime_root / "metadata.json"
    boot_epoch = windows_boot_epoch()
    metadata = {
        "schema_version": "1",
        "service": SERVICE_NAME,
        "host": host,
        "source_sha": source_sha,
        "runtime_root": str(runtime_root),
        "release_root": str(release_root),
        "python_executable": str(python_executable),
        "installed_at": now_iso(),
        "baseline_boot_epoch": boot_epoch,
        "watch_interval_seconds": DEFAULT_WATCH_SECONDS,
        "smoke_interval_seconds": DEFAULT_SMOKE_SECONDS,
        "profile": {
            "primary_model": profile["CODEX_OLLAMA_MODEL"],
            "fallback_model": profile["CODEX_OLLAMA_FALLBACK_MODEL"],
            "base_url": profile["CODEX_OLLAMA_BASE_URL"],
        },
    }
    atomic_json(metadata_file, metadata)
    launcher = _write_launcher(runtime_root)
    action = _task_action(python_executable, launcher)
    was_healthy = all((probe_ollama(), probe_gateway(), probe_backend()))
    registration = _register_task_via_base_python(
        release_supervisor=supervisor,
        python_executable=python_executable,
        launcher=launcher,
    )
    verified_task = (
        task_status()
        if registration.returncode == 0
        else {"exists": False, "trigger_at_startup": False}
    )
    task_ok = (
        registration.returncode == 0
        and verified_task.get("exists") is True
        and verified_task.get("trigger_at_startup") is True
    )
    persistence_mode = "task_at_startup_no_password" if task_ok else "hkcu_run_at_logon"
    requires_user_logon = not task_ok
    task_error = None
    if task_ok:
        _remove_run_key()
    else:
        _install_run_key(action)
        task_error = (
            registration.stderr
            or registration.stdout
            or "task_at_startup_not_verified"
        )[:500]

    if not was_healthy:
        if task_ok:
            _run_schtasks(["/Run", "/TN", TASK_NAME])
        else:
            subprocess.Popen(
                [str(python_executable), str(launcher)],
                cwd=str(release_root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=_creationflags(),
            )

    deadline = time.monotonic() + 45
    status_payload: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        time.sleep(1)
        status_payload = runtime_status(metadata_file)
        if status_payload.get("runtime_healthy"):
            break
    if not status_payload or not status_payload.get("runtime_healthy"):
        raise SupervisorError("supervisor instalado, mas runtime não ficou saudável")

    metadata.update(
        {
            "persistence_mode": persistence_mode,
            "requires_user_logon": requires_user_logon,
            "task_registration_error": task_error,
        }
    )
    atomic_json(metadata_file, metadata)
    return {
        "ok": True,
        "result": "CODEX_PC24X7_SUPERVISOR_INSTALLED",
        "metadata": metadata,
        "task": task_status(),
        "run_key": run_key_status(),
        "runtime": status_payload,
        "runtime_reused": was_healthy,
        "headless_24x7": persistence_mode == "task_at_startup_no_password",
        "production_touched": False,
        "deploy_performed": False,
    }


def runtime_status(metadata_file: Path) -> dict[str, Any]:
    if not metadata_file.is_file():
        return {"ok": False, "installed": False, "runtime_healthy": False}
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    root = Path(metadata["runtime_root"])
    state_file = root / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else None
    health = {
        "ollama": probe_ollama(),
        "gateway": probe_gateway(),
        "backend": probe_backend(),
    }
    return {
        "ok": all(health.values()),
        "installed": True,
        "runtime_healthy": all(health.values()),
        "metadata": metadata,
        "state": state,
        "health": health,
        "task": task_status(),
        "run_key": run_key_status(),
    }


def postboot_check(metadata_file: Path, require_reboot: bool) -> tuple[int, dict[str, Any]]:
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    baseline = int(metadata["baseline_boot_epoch"])
    current = windows_boot_epoch()
    reboot_observed = abs(current - baseline) > 120
    status = runtime_status(metadata_file)
    smoke_file = Path(metadata["runtime_root"]) / "last-smoke.json"
    smoke = json.loads(smoke_file.read_text(encoding="utf-8")) if smoke_file.is_file() else None
    ready = (
        reboot_observed
        and status.get("runtime_healthy") is True
        and smoke is not None
        and metadata.get("persistence_mode") == "task_at_startup_no_password"
    )
    payload = {
        "ok": ready if require_reboot else status.get("runtime_healthy") is True,
        "host": socket.gethostname(),
        "baseline_boot_epoch": baseline,
        "current_boot_epoch": current,
        "reboot_observed": reboot_observed,
        "runtime_healthy": status.get("runtime_healthy"),
        "persistence_mode": metadata.get("persistence_mode"),
        "requires_user_logon": metadata.get("requires_user_logon"),
        "smoke": smoke,
        "ready_postboot": ready,
        "generated_at": now_iso(),
    }
    atomic_json(Path(metadata["runtime_root"]) / "postboot-evidence.json", payload)
    if require_reboot and not reboot_observed:
        return 4, payload
    if require_reboot and metadata.get("persistence_mode") != "task_at_startup_no_password":
        return 5, payload
    if require_reboot and not status.get("runtime_healthy"):
        return 6, payload
    if require_reboot and smoke is None:
        return 7, payload
    return (0 if payload["ok"] else 2), payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Supervisor PC24x7 Codex/Ollama")
    sub = parser.add_subparsers(dest="command", required=True)

    install_parser = sub.add_parser("install")
    install_parser.add_argument("--source-root", type=Path, required=True)
    install_parser.add_argument("--source-sha", required=True)
    install_parser.add_argument("--python-executable", type=Path, required=True)
    install_parser.add_argument("--runtime-root", type=Path)

    for name in ("watch", "once", "status"):
        p = sub.add_parser(name)
        p.add_argument("--metadata", type=Path, required=True)

    register = sub.add_parser("register-task-com")
    register.add_argument("--python-executable", type=Path, required=True)
    register.add_argument("--launcher", type=Path, required=True)

    post = sub.add_parser("postboot-check")
    post.add_argument("--metadata", type=Path, required=True)
    post.add_argument("--require-reboot", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "install":
            result = install(
                args.source_root.resolve(),
                source_sha=args.source_sha,
                python_executable=args.python_executable.resolve(),
                runtime_root=(args.runtime_root or default_runtime_root()).resolve(),
            )
            print(json.dumps(result, ensure_ascii=True, sort_keys=True))
            return 0
        if args.command == "register-task-com":
            result = register_task_com(
                python_executable=args.python_executable.resolve(),
                launcher=args.launcher.resolve(),
            )
            print(json.dumps(result, ensure_ascii=True, sort_keys=True))
            return 0
        if args.command == "status":
            result = runtime_status(args.metadata.resolve())
            print(json.dumps(result, ensure_ascii=True, sort_keys=True))
            return 0 if result.get("runtime_healthy") else 3
        if args.command == "postboot-check":
            code, result = postboot_check(args.metadata.resolve(), args.require_reboot)
            print(json.dumps(result, ensure_ascii=True, sort_keys=True))
            return code

        require_windows_desktop()
        supervisor = Supervisor(args.metadata.resolve())
        if args.command == "once":
            result = supervisor.cycle(force_smoke=True)
            print(json.dumps(result, ensure_ascii=True, sort_keys=True))
            return 0
        return supervisor.watch()
    except (OSError, SupervisorError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc)[:1000],
                    "error_type": type(exc).__name__,
                    "production_touched": False,
                    "deploy_performed": False,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
