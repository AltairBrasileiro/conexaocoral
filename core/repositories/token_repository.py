from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from core.models import TokenWhitelist
from core.repositories.base import BaseRepository


class TokenWhitelistRepository(BaseRepository[TokenWhitelist]):
    model = TokenWhitelist

    def registrar(self, *, usuario_id: int, jti: str, tipo_token: str, expira_em: datetime) -> TokenWhitelist:
        return self.model.objects.create(
            usuario_id=usuario_id, jti=jti, tipo_token=tipo_token, expira_em=expira_em,
        )

    def esta_valido(self, jti: str, tipo_token: str) -> bool:
        """Token está na whitelist e ainda não expirou."""
        return self.model.objects.filter(
            jti=jti, tipo_token=tipo_token, expira_em__gt=timezone.now(),
        ).exists()

    def remover_jtis(self, *jtis: str) -> int:
        removidos, _ = self.model.objects.filter(jti__in=[j for j in jtis if j]).delete()
        return removidos

    def remover_todos_do_usuario(self, usuario_id: int) -> int:
        removidos, _ = self.model.objects.filter(usuario_id=usuario_id).delete()
        return removidos

    def remover_expirados(self) -> int:
        removidos, _ = self.model.objects.filter(expira_em__lte=timezone.now()).delete()
        return removidos
