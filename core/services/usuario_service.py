from __future__ import annotations

from typing import Any

from django.db import transaction

from core.exceptions import ConflitoError, PermissaoNegadaError
from core.models import TipoUsuario, Usuario
from core.repositories import UsuarioRepository


class UsuarioService:
    # Papéis que podem ser escolhidos no auto-cadastro (ADMIN nunca).
    PAPEIS_AUTOCADASTRO = frozenset({
        TipoUsuario.TORCEDOR,
        TipoUsuario.RESPONSAVEL_CONSULADO,
        TipoUsuario.RESPONSAVEL_ALIADO,
    })

    def __init__(self, repositorio: UsuarioRepository | None = None) -> None:
        self.repositorio = repositorio or UsuarioRepository()

    def validar_registro(self, *, email: str, tipo_usuario: str) -> None:
        if tipo_usuario not in self.PAPEIS_AUTOCADASTRO:
            raise PermissaoNegadaError("Tipo de usuário não permitido no cadastro.", campo="tipo_usuario")
        if self.repositorio.email_em_uso(email):
            raise ConflitoError("Já existe um usuário com este e-mail.", campo="email")

    @transaction.atomic
    def registrar(self, *, email: str, password: str, **dados: Any) -> Usuario:
        dados.setdefault("tipo_usuario", TipoUsuario.TORCEDOR)
        self.validar_registro(email=email, tipo_usuario=dados["tipo_usuario"])
        return self.repositorio.criar_usuario(email=email, password=password, **dados)
