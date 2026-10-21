from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from core.filters import CheckInFilter
from core.models import CheckIn
from core.permissions import IsDonoOuAdmin
from core.repositories import CheckInRepository
from core.serializers import CheckInSerializer
from core.services import CheckInService
from core.views.mixins import PermissaoPorAcaoMixin


class CheckInViewSet(
    PermissaoPorAcaoMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Check-ins em consulados durante partidas.

    Não há update/delete: um check-in é cancelado via ``POST /checkins/{id}/cancelar/``
    (mantém histórico e libera um novo check-in na mesma partida).
    """

    serializer_class = CheckInSerializer
    permission_classes = (IsAuthenticated,)
    permission_classes_por_acao = {"cancelar": [IsDonoOuAdmin]}
    filterset_class = CheckInFilter
    ordering_fields = ("data_checkin",)
    campo_dono = "usuario_id"

    service = CheckInService()

    def get_queryset(self) -> QuerySet[CheckIn]:
        if getattr(self, "swagger_fake_view", False):  # geração do schema OpenAPI
            return CheckIn.objects.none()
        return CheckInRepository().visiveis_para(self.request.user)

    def perform_create(self, serializer: CheckInSerializer) -> None:
        dados = serializer.validated_data
        serializer.instance = self.service.realizar_checkin(
            self.request.user, dados["partida"], dados["consulado"],
        )

    @action(detail=True, methods=["post"])
    def cancelar(self, request: Request, pk: str | None = None) -> Response:
        checkin = self.service.cancelar_checkin(self.get_object(), request.user)
        return Response(self.get_serializer(checkin).data)
