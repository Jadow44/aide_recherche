from __future__ import annotations

from typing import List, Optional


class Autor:
    def __init__(self, nome: str, link: Optional[str]):
        self.nome = nome
        self.artigos: List["Artigo"] = []
        self.link = link

    def addArtigo(self, artigo: "Artigo") -> None:
        self.artigos.append(artigo)
        self.artigos.sort()

    def _other_name(self, other: object) -> Optional[str]:
        if isinstance(other, Autor):
            return other.nome
        if isinstance(other, str):
            return other
        return None

    def __lt__(self, other: object) -> bool:
        other_name = self._other_name(other)
        if other_name is None:
            return NotImplemented
        return self.nome < other_name

    def __le__(self, other: object) -> bool:
        other_name = self._other_name(other)
        if other_name is None:
            return NotImplemented
        return self.nome <= other_name

    def __gt__(self, other: object) -> bool:
        other_name = self._other_name(other)
        if other_name is None:
            return NotImplemented
        return self.nome > other_name

    def __ge__(self, other: object) -> bool:
        other_name = self._other_name(other)
        if other_name is None:
            return NotImplemented
        return self.nome >= other_name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Autor):
            return NotImplemented
        return (self.nome, self.link) == (other.nome, other.link)

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return NotImplemented
        return not result

    def __hash__(self) -> int:
        return hash((self.nome, self.link))


# circular import friendly type checking
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - hints for type checkers only
    from Artigo import Artigo
