"""Permissões customizadas baseadas em papéis."""
from core.permissions.roles import (
    BaseRolePermission,
    IsAdminOrReadOnly,
    IsAdministrador,
    IsDonoOuAdmin,
    IsResponsavelAliado,
    IsResponsavelConsulado,
    IsTorcedor,
)

__all__ = [
    "BaseRolePermission",
    "IsAdminOrReadOnly",
    "IsAdministrador",
    "IsDonoOuAdmin",
    "IsResponsavelAliado",
    "IsResponsavelConsulado",
    "IsTorcedor",
]
