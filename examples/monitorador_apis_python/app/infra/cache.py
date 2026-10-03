import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class ItemCache(Generic[T]):
    valor: T
    expira_em: float


class CacheTTL(Generic[T]):
    def __init__(self, ttl_segundos: int):
        self.ttl_segundos = ttl_segundos
        self._dados: dict[str, ItemCache[T]] = {}

    def obter(self, chave: str) -> T | None:
        item = self._dados.get(chave)

        if item is None:
            return None

        if time.time() > item.expira_em:
            del self._dados[chave]
            return None

        return item.valor

    def salvar(self, chave: str, valor: T) -> None:
        self._dados[chave] = ItemCache(
            valor=valor,
            expira_em=time.time() + self.ttl_segundos,
        )

    def limpar(self) -> None:
        self._dados.clear()
