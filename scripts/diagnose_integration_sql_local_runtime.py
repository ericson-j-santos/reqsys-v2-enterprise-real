#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys


def registry_instances() -> list[str]:
    if sys.platform != "win32":
        return []
    import winreg

    instances: set[str] = set()
    base = r"SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL"
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base, 0, winreg.KEY_READ | view) as key:
                index = 0
                while True:
                    try:
                        name, _value, _kind = winreg.EnumValue(key, index)
                    except OSError:
                        break
                    instances.add(str(name))
                    index += 1
        except OSError:
            continue
    return sorted(instances)


def main() -> int:
    try:
        import pyodbc
    except ImportError:
        print(json.dumps({"status": "blocked", "reason": "pyodbc_ausente"}))
        return 2

    drivers = pyodbc.drivers()
    preferred = [name for name in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server") if name in drivers]
    instances = registry_instances()
    tools = {name: bool(shutil.which(name)) for name in ("sqlcmd", "sqllocaldb", "sqlservr")}

    attempts = []
    if preferred:
        driver = preferred[0]
        candidates = ["localhost", r".\SQLEXPRESS", r"(localdb)\MSSQLLocalDB"]
        candidates.extend(f"localhost\\{name}" for name in instances if name.casefold() != "mssqlserver")
        if any(name.casefold() == "mssqlserver" for name in instances):
            candidates.append("localhost")
        seen: set[str] = set()
        for server in candidates:
            if server.casefold() in seen:
                continue
            seen.add(server.casefold())
            connection = None
            try:
                dsn = (
                    f"Driver={{{driver}}};Server={server};Database=master;"
                    "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
                )
                connection = pyodbc.connect(dsn, timeout=3)
                attempts.append({"server": server, "connected": True, "sqlstate": None})
            except Exception as exc:
                state = str(exc.args[0]) if getattr(exc, "args", None) else exc.__class__.__name__
                attempts.append({"server": server, "connected": False, "sqlstate": state[:32]})
            finally:
                if connection is not None:
                    connection.close()

    connected = [item["server"] for item in attempts if item["connected"]]
    payload = {
        "status": "passed" if connected else "blocked",
        "pyodbc_version": getattr(pyodbc, "version", "unknown"),
        "sql_odbc_drivers": preferred,
        "sql_instances": instances,
        "tools_present": tools,
        "connection_attempts": attempts,
        "connected_servers": connected,
        "secret_exposed": False,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if connected else 2


if __name__ == "__main__":
    raise SystemExit(main())
