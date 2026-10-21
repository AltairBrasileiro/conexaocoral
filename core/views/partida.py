from __future__ import annotations

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from core.filters import PartidaFilter
from core.models import Partida
from core.permissions import IsAdminOrReadOnly
from core.serializers import PartidaSerializer, RankingConsuladoSerializer
from core.services import PartidaService


class PartidaViewSet(viewsets.ModelViewSet):
    """Calendário de partidas: leitura para todos, escrita apenas para admin."""

    queryset = Partida.objects.all()
    serializer_class = PartidaSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = PartidaFilter
    search_fields = ("adversario", "campeonato")
    ordering_fields = ("data_hora", "campeonato")
    ordering = ("data_hora",)

    service = PartidaService()

    @action(detail=False, methods=["get"])
    def proximas(self, request: Request) -> Response:
        """Próximas partidas (padrão: 10; use ?limite=N, máximo 50)."""
        try:
            limite = max(1, min(int(request.query_params.get("limite", 10)), 50))
        except ValueError:
            limite = 10
        serializer = self.get_serializer(self.service.proximas_partidas(limite), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="ranking-consulados", serializer_class=RankingConsuladoSerializer)
    def ranking_consulados(self, request: Request, pk: str | None = None) -> Response:
        """Consulados com mais check-ins ativos na partida."""
        qs = self.service.ranking_consulados(self.get_object())
        return Response(self.get_serializer(qs, many=True).data)
