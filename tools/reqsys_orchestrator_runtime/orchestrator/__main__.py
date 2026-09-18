from __future__ import annotations

import argparse
import json
import os

from .core import OrchestratorStore
from .server import build_server


def main() -> None:
    parser = argparse.ArgumentParser(prog="reqsys-orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--host", default=os.getenv("ORCH_HOST", "127.0.0.1"))
    serve_parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("ORCH_PORT", "8787")),
    )
    serve_parser.add_argument(
        "--db-path",
        default=os.getenv("ORCH_DB_PATH", "data/orchestrator.db"),
    )

    sub.add_parser("snapshot")
    sub.add_parser("recover")
    args = parser.parse_args()

    if args.command == "serve":
        if args.port < 1 or args.port > 65535:
            raise SystemExit("port must be between 1 and 65535")
        server = build_server(args.host, args.port, args.db_path)
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return

    store = OrchestratorStore(os.getenv("ORCH_DB_PATH", "data/orchestrator.db"))
    if args.command == "snapshot":
        print(json.dumps(store.snapshot(), ensure_ascii=False, sort_keys=True))
    elif args.command == "recover":
        print(json.dumps(store.recover_expired_leases(), sort_keys=True))


if __name__ == "__main__":
    main()
