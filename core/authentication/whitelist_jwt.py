"""Autenticação JWT com verificação de whitelist."""
from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import Token

from core.services.token_service import TokenWhitelistService


class WhitelistJWTAuthentication(JWTAuthentication):
    """
    Além das validações padrão do simplejwt (assinatura, expiração, tipo),
    exige que o ``jti`` do access token esteja na whitelist. Assim o logout
    revoga o token imediatamente.
    """

    def get_validated_token(self, raw_token: bytes) -> Token:
        token = super().get_validated_token(raw_token)
        jti = token.get(api_settings.JTI_CLAIM)
        if not jti or not TokenWhitelistService().access_esta_valido(jti):
            raise InvalidToken("Token revogado ou inexistente na whitelist.")
        return token
