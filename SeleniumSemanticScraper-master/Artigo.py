from __future__ import annotations

from typing import List, Optional


class Artigo:
    def __init__(
        self,
        titulo: str,
        autores: List["Autor"],
        publicado: str,
        data: str,
        citacoes: str,
        link: str,
        cite: str,
        bibtex: str,
        synopsis: str,
        qualis: str,
    ):
        self.titulo = titulo
        self.autores = autores
        self.publicado_em = publicado
        self.data = data
        self.citacoes = citacoes
        self.data_relativa = 0
        self.citacoes_relativa = 0
        self.cite_label = 0
        self.total_factor = 0
        self.impact_factor = " "
        self.link = link
        self.cite = cite
        self.bibtex = bibtex
        self.synopsis = synopsis
        self.qualis = qualis
        self.relevance_score = 0.0
        self.concepts = []

    def _other_title(self, other: object) -> Optional[str]:
        if isinstance(other, Artigo):
            return other.titulo
        if isinstance(other, str):
            return other
        return None

    def __lt__(self, other: object) -> bool:
        other_title = self._other_title(other)
        if other_title is None:
            return NotImplemented
        return self.titulo < other_title

    def __le__(self, other: object) -> bool:
        other_title = self._other_title(other)
        if other_title is None:
            return NotImplemented
        return self.titulo <= other_title

    def __gt__(self, other: object) -> bool:
        other_title = self._other_title(other)
        if other_title is None:
            return NotImplemented
        return self.titulo > other_title

    def __ge__(self, other: object) -> bool:
        other_title = self._other_title(other)
        if other_title is None:
            return NotImplemented
        return self.titulo >= other_title

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Artigo):
            return NotImplemented
        return (self.titulo, self.link) == (other.titulo, other.link)

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return NotImplemented
        return not result

    def __hash__(self) -> int:
        return hash((self.titulo, self.link))


from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - hints for type checkers only
    from Autor import Autor
