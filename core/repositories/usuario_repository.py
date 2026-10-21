from __future__ import annotations

from typing import Any

from core.models import Usuario
from core.repositories.base import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    model = Usuario

    def email_em_uso(self, email: str, *, exceto_id: int | None = None) -> bool:
        qs = self.get_queryset().filter(email__iexact=email)
        if exceto_id is not None:
            qs = qs.exclude(pk=exceto_id)
        return qs.exists()

    def criar_usuario(self, *, email: str, password: str, **dados: Any) -> Usuario:
        # Usa o manager para garantir hash de senha e normalização de e-mail.
        return Usuario.objects.create_user(email=email, password=password, **dados)
