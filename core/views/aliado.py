from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from core.filters import AliadoFilter
from core.models import Aliado
from core.permissions import IsAdministrador, IsDonoOuAdmin
from core.repositories import AliadoRepository
from core.serializers import AliadoSerializer
from core.services import AliadoService
from core.views.mixins import PermissaoPorAcaoMixin


class AliadoViewSet(PermissaoPorAcaoMixin, viewsets.ModelViewSet):
    """
    Negócios aliados da torcida.

    * Criar: qualquer usuário (nasce PENDENTE; cadastro do admin já nasce aprovado).
    * Editar/excluir: dono ou admin (edição do dono volta para moderação).
    * Aprovar/rejeitar/selo: admin. Ao aprovar, o torcedor dono vira Responsável por Aliado.
    """

    serializer_class = AliadoSerializer
    filterset_class = AliadoFilter
    search_fields = ("nome_negocio", "descricao")
    ordering_fields = ("nome_negocio", "criado_em")
    campo_dono = "usuario_id"

    permission_classes = (IsAuthenticated,)
    permission_classes_por_acao = {
        "update": [IsDonoOuAdmin],
        "partial_update": [IsDonoOuAdmin],
        "destroy": [IsDonoOuAdmin],
        "aprovar": [IsAdministrador],
        "rejeitar": [IsAdministrador],
        "conceder_selo": [IsAdministrador],
        "revogar_selo": [IsAdministrador],
    }

    service = AliadoService()

    def get_queryset(self) -> QuerySet[Aliado]:
        if getattr(self, "swagger_fake_view", False):  # geração do schema OpenAPI
            return Aliado.objects.none()
        return AliadoRepository().visiveis_para(self.request.user)

    def perform_create(self, serializer: AliadoSerializer) -> None:
        serializer.instance = self.service.criar_aliado(self.request.user, **serializer.validated_data)

    def perform_update(self, serializer: AliadoSerializer) -> None:
        serializer.instance = self.service.atualizar_aliado(
            serializer.instance, self.request.user, **serializer.validated_data,
        )

    def perform_destroy(self, instance: Aliado) -> None:
        self.service.excluir_aliado(instance, self.request.user)

    @action(detail=True, methods=["post"])
    def aprovar(self, request: Request, pk: str | None = None) -> Response:
        aliado = self.service.aprovar(self.get_object(), moderador=request.user)
        return Response(self.get_serializer(aliado).data)

    @action(detail=True, methods=["post"])
    def rejeitar(self, request: Request, pk: str | None = None) -> Response:
        aliado = self.service.rejeitar(
            self.get_object(), moderador=request.user, motivo=str(request.data.get("motivo", "")),
        )
        return Response(self.get_serializer(aliado).data)

    @action(detail=True, methods=["post"], url_path="conceder-selo")
    def conceder_selo(self, request: Request, pk: str | None = None) -> Response:
        aliado = self.service.definir_selo(self.get_object(), verificado=True, moderador=request.user)
        return Response(self.get_serializer(aliado).data)

    @action(detail=True, methods=["post"], url_path="revogar-selo")
    def revogar_selo(self, request: Request, pk: str | None = None) -> Response:
        aliado = self.service.definir_selo(self.get_object(), verificado=False, moderador=request.user)
        return Response(self.get_serializer(aliado).data)
