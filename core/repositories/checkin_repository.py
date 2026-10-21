from __future__ import annotations

from django.db.models import Q, QuerySet

from core.models import CheckIn, Partida, Usuario
from core.repositories.base import BaseRepository


class CheckInRepository(BaseRepository[CheckIn]):
    model = CheckIn

    def get_queryset(self) -> QuerySet[CheckIn]:
        return super().get_queryset().select_related("usuario", "partida", "consulado")

    def visiveis_para(self, usuario: Usuario) -> QuerySet[CheckIn]:
        """Admin vê todos; o usuário vê os seus e os feitos nos consulados que administra."""
        qs = self.get_queryset()
        if usuario.is_admin:
            return qs
        return qs.filter(Q(usuario=usuario) | Q(consulado__responsavel=usuario))

    def existe_ativo(self, usuario: Usuario, partida: Partida) -> bool:
        return self.model.objects.filter(usuario=usuario, partida=partida, ativo=True).exists()
