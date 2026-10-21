from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from core.filters import EventoFilter
from core.models import Evento, PresencaEvento
from core.permissions import IsAdministrador, IsDonoOuAdmin, IsResponsavelConsulado
from core.repositories import EventoRepository, PresencaEventoRepository
from core.serializers import EventoSerializer, PresencaEventoSerializer
from core.services import EventoService
from core.views.mixins import ModeracaoMixin, PermissaoPorAcaoMixin


class EventoViewSet(PermissaoPorAcaoMixin, ModeracaoMixin, viewsets.ModelViewSet):
    """
    Eventos dos consulados.

    * Criar: Responsável por Consulado (só no próprio consulado; nasce PENDENTE).
    * Editar/excluir: responsável pelo consulado organizador ou admin.
    * Aprovar/rejeitar: admin.
    * Eventos exclusivos só são listados para membros do consulado.
    """

    serializer_class = EventoSerializer
    filterset_class = EventoFilter
    search_fields = ("titulo", "descricao", "consulado__nome")
    ordering_fields = ("data_hora_inicio", "criado_em", "total_confirmados")
    # Explícito: consultas com Count (total_confirmados) ignoram o Meta.ordering do model.
    ordering = ("data_hora_inicio",)
    campo_dono = "consulado.responsavel_id"

    permission_classes = (IsAuthenticated,)
    permission_classes_por_acao = {
        "create": [IsResponsavelConsulado],
        "update": [IsDonoOuAdmin],
        "partial_update": [IsDonoOuAdmin],
        "destroy": [IsDonoOuAdmin],
        "presencas": [IsDonoOuAdmin],
        "aprovar": [IsAdministrador],
        "rejeitar": [IsAdministrador],
    }

    service = EventoService()

    def get_queryset(self) -> QuerySet[Evento]:
        if getattr(self, "swagger_fake_view", False):  # geração do schema OpenAPI
            return Evento.objects.none()
        return EventoRepository().visiveis_para(self.request.user)

    def perform_create(self, serializer: EventoSerializer) -> None:
        serializer.instance = self.service.criar_evento(self.request.user, **serializer.validated_data)

    def perform_update(self, serializer: EventoSerializer) -> None:
        serializer.instance = self.service.atualizar_evento(
            serializer.instance, self.request.user, **serializer.validated_data,
        )

    @action(detail=True, methods=["post"])
    def aprovar(self, request: Request, pk: str | None = None) -> Response:
        return self.aprovar_recurso(request)

    @action(detail=True, methods=["post"])
    def rejeitar(self, request: Request, pk: str | None = None) -> Response:
        return self.rejeitar_recurso(request)

    @action(detail=True, methods=["get"], serializer_class=PresencaEventoSerializer)
    def presencas(self, request: Request, pk: str | None = None) -> Response:
        """Lista de confirmados (responsável pelo consulado ou admin)."""
        qs = PresencaEventoRepository().do_evento(self.get_object())
        pagina = self.paginate_queryset(qs)
        serializer = self.get_serializer(pagina if pagina is not None else qs, many=True)
        return self.get_paginated_response(serializer.data) if pagina is not None else Response(serializer.data)


class PresencaEventoViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Confirmações de presença do usuário logado.

    POST exige que o usuário seja membro do consulado organizador.
    """

    serializer_class = PresencaEventoSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("evento",)
    ordering_fields = ("data_confirmacao",)

    service = EventoService()

    def get_queryset(self) -> QuerySet[PresencaEvento]:
        if getattr(self, "swagger_fake_view", False):
            return PresencaEvento.objects.none()
        return PresencaEventoRepository().visiveis_para(self.request.user)

    def perform_create(self, serializer: PresencaEventoSerializer) -> None:
        serializer.instance = self.service.confirmar_presenca(
            self.request.user, serializer.validated_data["evento"],
        )

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        self.service.cancelar_presenca(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
