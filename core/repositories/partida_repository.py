from __future__ import annotations

from django.db.models import QuerySet
from django.utils import timezone

from core.models import Partida
from core.repositories.base import BaseRepository


class PartidaRepository(BaseRepository[Partida]):
    model = Partida

    def proximas(self, limite: int = 10) -> QuerySet[Partida]:
        return self.get_queryset().filter(data_hora__gte=timezone.now()).order_by("data_hora")[:limite]

