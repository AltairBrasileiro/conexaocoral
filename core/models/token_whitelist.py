"""Whitelist de tokens JWT emitidos (controle de sessões ativas)."""
from django.conf import settings
from django.db import models


class TokenWhitelist(models.Model):
    """
    Cada linha representa um token JWT válido.

    Um token só é aceito se sua assinatura for válida E seu ``jti`` constar
    aqui. Remover a linha revoga o token na hora (logout).
    """

    class TipoToken(models.TextChoices):
        ACCESS = "access", "Access"
        REFRESH = "refresh", "Refresh"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tokens_whitelist",
    )
    jti = models.CharField("JWT ID", max_length=255, unique=True)
    tipo_token = models.CharField("tipo", max_length=10, choices=TipoToken.choices)
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = "token na whitelist"
        verbose_name_plural = "tokens na whitelist"
        ordering = ("-criado_em",)

    def __str__(self) -> str:
        return f"{self.tipo_token}:{self.jti} ({self.usuario_id})"
