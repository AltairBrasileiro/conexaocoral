from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from core.filters import ConsuladoFilter
from core.models import Consulado
from core.permissions import IsAdministrador, IsDonoOuAdmin, IsResponsavelConsulado
from core.repositories import ConsuladoRepository, MembroConsuladoRepository
from core.serializers import ConsuladoSerializer, MembroConsuladoSerializer
from core.services import ConsuladoService
from core.views.mixins import ModeracaoMixin, PermissaoPorAcaoMixin


class ConsuladoViewSet(PermissaoPorAcaoMixin, ModeracaoMixin, viewsets.ModelViewSet):
    """
    CRUD de consulados.

    * Listar/detalhar: qualquer autenticado (vê aprovados + os que administra).
    * Criar: Responsável por Consulado (nasce PENDENTE).
    * Editar/excluir: dono ou admin.
    * Aprovar/rejeitar: admin.
    """

    serializer_class = ConsuladoSerializer
    filterset_class = ConsuladoFilter
    search_fields = ("nome", "endereco", "descricao")
    ordering_fields = ("nome", "criado_em", "total_membros")
    # Explícito: consultas com Count (total_membros) ignoram o Meta.ordering do model.
    ordering = ("nome",)
    campo_dono = "responsavel_id"

    permission_classes = (IsAuthenticated,)
    permission_classes_por_acao = {
        "create": [IsResponsavelConsulado],
        "update": [IsDonoOuAdmin],
        "partial_update": [IsDonoOuAdmin],
        "destroy": [IsDonoOuAdmin],
        "membros": [IsDonoOuAdmin],
        "aprovar": [IsAdministrador],
        "rejeitar": [IsAdministrador],
    }

    service = ConsuladoService()

    def get_queryset(self) -> QuerySet[Consulado]:
        if getattr(self, "swagger_fake_view", False):  # geração do schema OpenAPI
            return Consulado.objects.none()
        return ConsuladoRepository().visiveis_para(self.request.user)

    def perform_create(self, serializer: ConsuladoSerializer) -> None:
        serializer.instance = self.service.criar_consulado(self.request.user, **serializer.validated_data)

    @action(detail=True, methods=["post"])
    def aprovar(self, request: Request, pk: str | None = None) -> Response:
        return self.aprovar_recurso(request)

    @action(detail=True, methods=["post"])
    def rejeitar(self, request: Request, pk: str | None = None) -> Response:
        return self.rejeitar_recurso(request)

    @action(detail=True, methods=["get"], serializer_class=MembroConsuladoSerializer)
    def membros(self, request: Request, pk: str | None = None) -> Response:
        """Lista paginada de membros (apenas responsável ou admin)."""
        consulado = self.get_object()
        qs = MembroConsuladoRepository().membros_do_consulado(consulado)
        pagina = self.paginate_queryset(qs)
        serializer = self.get_serializer(pagina if pagina is not None else qs, many=True)
        return self.get_paginated_response(serializer.data) if pagina is not None else Response(serializer.data)

    @action(detail=True, methods=["post"])
    def sair(self, request: Request, pk: str | None = None) -> Response:
        """O usuário logado deixa de ser membro do consulado."""
        self.service.sair_do_consulado(request.user, self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)
