"""Mixins reutilizáveis nos ViewSets."""
from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from core.services import AprovacaoService


class PermissaoPorAcaoMixin:
    """
    Permite declarar permissões diferentes para cada action:

        permission_classes_por_acao = {
            "create": [IsResponsavelConsulado],
            "destroy": [IsDonoOuAdmin],
        }

    Actions não mapeadas usam ``permission_classes``.
    """

    permission_classes_por_acao: dict[str, list[type[BasePermission]]] = {}

    def get_permissions(self) -> list[BasePermission]:
        classes = self.permission_classes_por_acao.get(self.action)  # type: ignore[attr-defined]
        if classes is None:
            return super().get_permissions()  # type: ignore[misc]
        return [permissao() for permissao in classes]


class ModeracaoMixin:
    """Actions ``aprovar`` e ``rejeitar`` para recursos aprováveis (usa get_object)."""

    aprovacao_service = AprovacaoService()

    def _moderar(self, request: Request, metodo: str) -> Response:
        instancia = self.get_object()  # type: ignore[attr-defined]
        getattr(self.aprovacao_service, metodo)(instancia, moderador=request.user)
        serializer = self.get_serializer(instancia)  # type: ignore[attr-defined]
        return Response(serializer.data, status=status.HTTP_200_OK)

    def aprovar_recurso(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._moderar(request, "aprovar")

    def rejeitar_recurso(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._moderar(request, "rejeitar")
