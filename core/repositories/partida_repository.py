from __future__ import annotations

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from core.models import Consulado, Partida
from core.repositories.base import BaseRepository


class PartidaRepository(BaseRepository[Partida]):
    model = Partida

    def proximas(self, limite: int = 10) -> QuerySet[Partida]:
        return self.get_queryset().filter(data_hora__gte=timezone.now()).order_by("data_hora")[:limite]

    def ranking_consulados(self, partida: Partida) -> QuerySet[Consulado]:
        """Consulados ordenados pela quantidade de check-ins ativos na partida."""
        filtro = Q(checkins__partida=partida, checkins__ativo=True)
        return (
            Consulado.objects.annotate(total_checkins=Count("checkins", filter=filtro))
            .filter(total_checkins__gt=0)
            .order_by("-total_checkins", "nome")
        )
