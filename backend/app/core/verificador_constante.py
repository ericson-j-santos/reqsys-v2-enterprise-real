from __future__ import annotations

import hmac


def comparar_constante(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))
