from __future__ import annotations

from inspect import isawaitable
from typing import Any, TypeVar, cast

T = TypeVar("T")


async def resolve_maybe_awaitable(value: T | Any) -> T:
    """Resolve contratos que podem ser síncronos (memória) ou assíncronos (Redis)."""
    if isawaitable(value):
        return cast(T, await value)
    return cast(T, value)
