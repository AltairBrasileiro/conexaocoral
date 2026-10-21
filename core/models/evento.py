"""Models de Evento e PresencaEvento."""
from django.conf import settings
from django.db import models
from django.db.models import F, Q

from core.models.base import AprovavelModel


class Evento(AprovavelModel):
    consulado = models.ForeignKey(
        "core.Consulado", on_delete=models.CASCADE, related_name="eventos", verbose_name="consulado",
    )
    titulo = models.CharField("título", max_length=150)
    descricao = models.TextField("descrição", blank=True)
    data_hora_inicio = models.DateTimeField("início", db_index=True)
    data_hora_fim = models.DateTimeField("fim")
    exclusivo_membros = models.BooleanField("exclusivo para membros", default=False)

    class Meta:
        verbose_name = "evento"
        verbose_name_plural = "eventos"
        ordering = ("data_hora_inicio",)
        constraints = [
            models.CheckConstraint(
                condition=Q(data_hora_fim__gt=F("data_hora_inicio")),
                name="ck_evento_fim_depois_inicio",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.consulado})"


class PresencaEvento(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="presencas", verbose_name="usuário",
    )
    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name="presencas", verbose_name="evento",
    )
    data_confirmacao = models.DateTimeField("data de confirmação", auto_now_add=True)

    class Meta:
        verbose_name = "presença em evento"
        verbose_name_plural = "presenças em eventos"
        ordering = ("-data_confirmacao",)
        constraints = [
            models.UniqueConstraint(fields=["usuario", "evento"], name="uq_presenca_usuario_evento"),
        ]

    def __str__(self) -> str:
        return f"{self.usuario} confirmou {self.evento}"
