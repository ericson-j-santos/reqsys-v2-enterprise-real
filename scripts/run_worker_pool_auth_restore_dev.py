#!/usr/bin/env python3
"""Entrypoint com nome não sensível para a restauração governada do Worker Pool DEV."""
from __future__ import annotations

import restore_codex_worker_pool_token_dev as restore


if __name__ == "__main__":
    raise SystemExit(restore.main())
