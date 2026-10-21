from __future__ import annotations

from django.db.models import QuerySet

from core.models import Consulado, Partida
from core.repositories import PartidaRepository


class PartidaService:
    def __init__(self, repositorio: PartidaRepository | None = None) -> None:
        self.repositorio = repositorio or PartidaRepository()

    def proximas_partidas(self, limite: int = 10) -> QuerySet[Partida]:
        return self.repositorio.proximas(limite)

    def ranking_consulados(self, partida: Partida) -> QuerySet[Consulado]:
        return self.repositorio.ranking_consulados(partida)
