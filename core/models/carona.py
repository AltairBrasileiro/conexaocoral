"""Models da Carona Coral: oferta de carona entre membros de um consulado e suas reservas."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from core.models.base import TimeStampedModel

MAXIMO_VAGAS_CARONA = 50
MAXIMO_CARACTERES_CARONA = 500


class Carona(TimeStampedModel):
    """
    Carona oferecida a membros do consulado (ida ao estádio, a um evento...).

    Fica visível só para os membros do consulado e aceita reservas até ``expira_em``.
    """

    consulado = models.ForeignKey(
        "core.Consulado", on_delete=models.CASCADE, related_name="caronas", verbose_name="consulado",
    )
    motorista = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="caronas_oferecidas",
        verbose_name="quem oferece",
    )
    descricao = models.CharField("descrição", max_length=MAXIMO_CARACTERES_CARONA)
    vagas = models.PositiveSmallIntegerField(
        "vagas", validators=[MinValueValidator(1), MaxValueValidator(MAXIMO_VAGAS_CARONA)],
    )
    data_hora_encontro = models.DateTimeField("data e hora do encontro", db_index=True)
    # Depois deste momento a oferta não aceita reservas e some para os membros.
    expira_em = models.DateTimeField("oferta válida até", db_index=True)

    class Meta:
        verbose_name = "carona"
        verbose_name_plural = "caronas"
        ordering = ("data_hora_encontro",)
        constraints = [
            models.CheckConstraint(
                condition=Q(expira_em__lte=F("data_hora_encontro")),
                name="ck_carona_expira_ate_o_encontro",
            ),
            models.CheckConstraint(
                condition=Q(vagas__gte=1) & Q(vagas__lte=MAXIMO_VAGAS_CARONA),
                name="ck_carona_vagas_validas",
            ),
        ]

    def __str__(self) -> str:
        return f"Carona de {self.motorista.nome} ({self.consulado}) - {self.data_hora_encontro:%d/%m/%Y %H:%M}"


class ReservaAtivaManager(models.Manager):
    """Esconde as reservas retiradas por quem oferece a carona (listas, contagens, ``carona.reservas``)."""

    def get_queryset(self):
        return super().get_queryset().filter(removida_em__isnull=True)


class ReservaCarona(models.Model):
    """Vaga reservada por um membro; o check-in é registrado por quem oferece a carona."""

    carona = models.ForeignKey(Carona, on_delete=models.CASCADE, related_name="reservas", verbose_name="carona")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reservas_carona",
        verbose_name="passageiro",
    )
    reservado_em = models.DateTimeField("reservado em", auto_now_add=True)
    checkin_em = models.DateTimeField("check-in em", null=True, blank=True)
    checkin_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="check-in feito por",
    )
    # Retirada por quem oferece a carona: o registro fica para impedir que a
    # pessoa reserve de novo na mesma carona (até ser readmitida).
    removida_em = models.DateTimeField("retirada em", null=True, blank=True)
    removida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="retirada por",
    )

    objects = ReservaAtivaManager()
    todas = models.Manager()

    class Meta:
        base_manager_name = "todas"
        verbose_name = "reserva de carona"
        verbose_name_plural = "reservas de carona"
        ordering = ("reservado_em",)
        constraints = [
            models.UniqueConstraint(fields=["carona", "usuario"], name="uq_reserva_carona_usuario"),
        ]

    def __str__(self) -> str:
        return f"{self.usuario} → {self.carona}"
