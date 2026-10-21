from __future__ import annotations

from django.db.models import Q, QuerySet

from core.models import Aliado, StatusAprovacao, Usuario
from core.repositories.base import BaseRepository


class AliadoRepository(BaseRepository[Aliado]):
    model = Aliado

    def get_queryset(self) -> QuerySet[Aliado]:
        return super().get_queryset().select_related("usuario")

    def visiveis_para(self, usuario: Usuario) -> QuerySet[Aliado]:
        qs = self.get_queryset()
        if usuario.is_admin:
            return qs
        return qs.filter(Q(status_aprovacao=StatusAprovacao.APROVADO) | Q(usuario=usuario))
