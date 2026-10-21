"""
Gerenciamento da whitelist de JWT.

Fluxo:
    login   -> registra access + refresh
    refresh -> valida refresh na whitelist, remove o antigo, registra os novos
    logout  -> remove o refresh informado e o access da requisição
"""
from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from django.db import transaction
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken, Token

from core.models import TokenWhitelist
from core.repositories import TokenWhitelistRepository


class TokenWhitelistService:
    def __init__(self, repositorio: TokenWhitelistRepository | None = None) -> None:
        self.repositorio = repositorio or TokenWhitelistRepository()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _expiracao(token: Token) -> datetime:
        return datetime.fromtimestamp(token["exp"], tz=dt_timezone.utc)

    def _registrar(self, token: Token, tipo: str) -> None:
        self.repositorio.registrar(
            usuario_id=token[api_settings.USER_ID_CLAIM],
            jti=token[api_settings.JTI_CLAIM],
            tipo_token=tipo,
            expira_em=self._expiracao(token),
        )

    # ------------------------------------------------------------------ comandos
    @transaction.atomic
    def registrar_par(self, *, refresh: str, access: str) -> None:
        """Registra na whitelist os tokens recém-emitidos (strings já assinadas)."""
        self._registrar(RefreshToken(refresh), TokenWhitelist.TipoToken.REFRESH)
        self._registrar(AccessToken(access), TokenWhitelist.TipoToken.ACCESS)

    @transaction.atomic
    def rotacionar(self, *, refresh_antigo_jti: str, access: str, refresh: str | None = None) -> None:
        """Remove o refresh usado e registra os tokens emitidos no refresh."""
        self.repositorio.remover_jtis(refresh_antigo_jti)
        self._registrar(AccessToken(access), TokenWhitelist.TipoToken.ACCESS)
        if refresh:
            self._registrar(RefreshToken(refresh), TokenWhitelist.TipoToken.REFRESH)

    def refresh_esta_valido(self, jti: str) -> bool:
        return self.repositorio.esta_valido(jti, TokenWhitelist.TipoToken.REFRESH)

    def access_esta_valido(self, jti: str) -> bool:
        return self.repositorio.esta_valido(jti, TokenWhitelist.TipoToken.ACCESS)

    def revogar(self, *jtis: str) -> int:
        return self.repositorio.remover_jtis(*jtis)

    def revogar_todos(self, usuario_id: int) -> int:
        return self.repositorio.remover_todos_do_usuario(usuario_id)

    def limpar_expirados(self) -> int:
        return self.repositorio.remover_expirados()
