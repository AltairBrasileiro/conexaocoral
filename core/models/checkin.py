"""Model de CheckIn de torcedor em um consulado durante uma partida."""
from django.conf import settings
from django.db import models
from django.db.models import Q


class CheckIn(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="checkins", verbose_name="usuário",
    )
    partida = models.ForeignKey(
        "core.Partida", on_delete=models.PROTECT, related_name="checkins", verbose_name="partida",
    )
    consulado = models.ForeignKey(
        "core.Consulado", on_delete=models.PROTECT, related_name="checkins", verbose_name="consulado",
    )
    data_checkin = models.DateTimeField("data do check-in", auto_now_add=True)
    # Permite cancelar um check-in (ex.: foi para outro consulado) sem perder o histórico.
    ativo = models.BooleanField("ativo", default=True, db_index=True)

    class Meta:
        verbose_name = "check-in"
        verbose_name_plural = "check-ins"
        ordering = ("-data_checkin",)
        constraints = [
            # Regra: no máximo 1 check-in ATIVO por usuário em cada partida.
            # Índice único parcial no PostgreSQL => proteção contra condição de corrida.
            models.UniqueConstraint(
                fields=["usuario", "partida"],
                condition=Q(ativo=True),
                name="uq_checkin_ativo_usuario_partida",
            ),
        ]
        indexes = [models.Index(fields=["partida", "consulado"], name="idx_checkin_partida_consulado")]

    def __str__(self) -> str:
        return f"{self.usuario} @ {self.consulado} ({self.partida})"
