from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from core.models import Usuario
from core.permissions import IsAdministrador
from core.serializers import UsuarioAdminSerializer, UsuarioSerializer
from core.services import TokenWhitelistService
from core.views.mixins import PermissaoPorAcaoMixin


class UsuarioViewSet(
    PermissaoPorAcaoMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Gestão de usuários (somente admin) + ``/usuarios/me/`` para o próprio perfil.

    Não há DELETE: usuários são desativados (``is_active=False``) para
    preservar o histórico de check-ins e presenças.
    """

    queryset = Usuario.objects.all().order_by("nome")
    serializer_class = UsuarioAdminSerializer
    permission_classes = (IsAdministrador,)
    permission_classes_por_acao = {"me": [IsAuthenticated]}
    filterset_fields = ("tipo_usuario", "is_active")
    search_fields = ("nome", "email")
    ordering_fields = ("nome", "criado_em")

    def perform_update(self, serializer: UsuarioAdminSerializer) -> None:
        usuario = serializer.save()
        # Desativar ou trocar o papel encerra as sessões (os claims do token mudaram).
        if {"is_active", "tipo_usuario"} & serializer.validated_data.keys():
            TokenWhitelistService().revogar_todos(usuario.id)

    @action(detail=False, methods=["get", "patch"], serializer_class=UsuarioSerializer)
    def me(self, request: Request) -> Response:
        """GET/PATCH do perfil do usuário logado."""
        if request.method == "GET":
            return Response(self.get_serializer(request.user).data)
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
