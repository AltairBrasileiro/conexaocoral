"""Model de Partida."""
from django.db import models

from core.models.choices import MandoCampo


class Partida(models.Model):
    adversario = models.CharField("adversário", max_length=100)
    mando_campo = models.CharField("mando de campo", max_length=4, choices=MandoCampo.choices)
    campeonato = models.CharField("campeonato", max_length=100, db_index=True)
    data_hora = models.DateTimeField("data e hora", db_index=True)
    canal_transmissao = models.CharField("canal de transmissão", max_length=100, blank=True)

    class Meta:
        verbose_name = "partida"
        verbose_name_plural = "partidas"
        ordering = ("data_hora",)

    def __str__(self) -> str:
        return f"{self.adversario} ({self.get_mando_campo_display()}) - {self.data_hora:%d/%m/%Y %H:%M}"
