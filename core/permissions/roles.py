"""
Permissões baseadas em papéis (RBAC).

Papéis: TORCEDOR, RESPONSAVEL_CONSULADO, RESPONSAVEL_ALIADO e ADMIN.
O administrador passa em todas as checagens de papel.
"""
from __future__ import annotations

from operator import attrgetter
from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from core.models import TipoUsuario


def _autenticado(request: Request) -> bool:
    return bool(request.user and request.user.is_authenticated)


class BaseRolePermission(BasePermission):
    """Libera o acesso se o usuário tiver um dos ``papeis_permitidos`` (ou for admin)."""

    papeis_permitidos: tuple[str, ...] = ()
    message = "Seu perfil de usuário não tem permissão para esta ação."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not _autenticado(request):
            return False
        return request.user.is_admin or request.user.tipo_usuario in self.papeis_permitidos


class IsAdministrador(BaseRolePermission):
    papeis_permitidos = (TipoUsuario.ADMIN,)
    message = "Apenas administradores podem executar esta ação."


class IsResponsavelConsulado(BaseRolePermission):
    papeis_permitidos = (TipoUsuario.RESPONSAVEL_CONSULADO,)
    message = "Apenas responsáveis por consulado podem executar esta ação."


class IsResponsavelAliado(BaseRolePermission):
    papeis_permitidos = (TipoUsuario.RESPONSAVEL_ALIADO,)
    message = "Apenas responsáveis por aliados podem executar esta ação."


class IsTorcedor(BaseRolePermission):
    papeis_permitidos = (TipoUsuario.TORCEDOR,)
    message = "Apenas torcedores podem executar esta ação."


class IsAdminOrReadOnly(BasePermission):
    """Leitura para qualquer autenticado; escrita somente para admin."""

    message = "Apenas administradores podem alterar este recurso."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not _autenticado(request):
            return False
        return request.method in SAFE_METHODS or request.user.is_admin


class IsDonoOuAdmin(BasePermission):
    """
    Permissão de objeto: libera se o usuário for o dono do recurso ou admin.

    A view informa como chegar ao ID do dono pelo atributo ``campo_dono``,
    aceitando caminhos pontilhados. Ex.: ``"responsavel_id"`` ou
    ``"consulado.responsavel_id"``.
    """

    message = "Você só pode alterar recursos que são seus."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return _autenticado(request)

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if request.user.is_admin:
            return True
        campo_dono = getattr(view, "campo_dono", "usuario_id")
        try:
            return attrgetter(campo_dono)(obj) == request.user.id
        except AttributeError:
            return False
