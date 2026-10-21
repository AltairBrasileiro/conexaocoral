"""Serializers de autenticação JWT integrados à whitelist."""
from __future__ import annotations

from typing import Any

from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Usuario
from core.serializers.usuario import UsuarioSerializer
from core.services import TokenWhitelistService


class LoginSerializer(TokenObtainPairSerializer):
    """Login por e-mail/senha. Adiciona claims úteis e os dados do usuário na resposta."""

    @classmethod
    def get_token(cls, user: Usuario) -> RefreshToken:
        token = super().get_token(user)
        # Claims customizadas (copiadas também para o access token).
        token["nome"] = user.nome
        token["tipo_usuario"] = user.tipo_usuario
        return token

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        data = super().validate(attrs)
        data["usuario"] = UsuarioSerializer(self.user).data
        return data


class WhitelistTokenRefreshSerializer(TokenRefreshSerializer):
    """Só aceita refresh tokens presentes na whitelist."""

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        try:
            refresh = RefreshToken(attrs["refresh"])
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc

        jti = refresh[api_settings.JTI_CLAIM]
        if not TokenWhitelistService().refresh_esta_valido(jti):
            raise InvalidToken("Refresh token revogado ou inexistente na whitelist.")

        data = super().validate(attrs)
        # Guardado para a view poder remover o refresh antigo da whitelist.
        self.refresh_antigo_jti = jti
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="Refresh token a ser revogado.")

    def validate_refresh(self, valor: str) -> str:
        try:
            self.refresh_jti = RefreshToken(valor)[api_settings.JTI_CLAIM]
        except TokenError as exc:
            raise serializers.ValidationError("Refresh token inválido ou expirado.") from exc
        return valor
