"""Models de Evento e PresencaEvento."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from core.models.base import AprovavelModel
from core.validators import upload_imagem_evento, validar_extensao_imagem, validar_tamanho_imagem


class Evento(AprovavelModel):
    consulado = models.ForeignKey(
        "core.Consulado", on_delete=models.CASCADE, related_name="eventos", verbose_name="consulado",
    )
    titulo = models.CharField("título", max_length=150)
    descricao = models.TextField("descrição", blank=True)
    data_hora_inicio = models.DateTimeField("início", db_index=True)
    data_hora_fim = models.DateTimeField("fim")
    exclusivo_membros = models.BooleanField("exclusivo para membros", default=False)
    # Opcional: para eventos com número de pessoas restrito (vazio = sem limite).
    limite_vagas = models.PositiveIntegerField(
        "limite de vagas", null=True, blank=True, validators=[MinValueValidator(1)],
    )

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


class FotoEvento(models.Model):
    """Foto de divulgação do evento (cartaz, local, edição anterior...)."""

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="fotos", verbose_name="evento")
    imagem = models.ImageField(
        "imagem", upload_to=upload_imagem_evento, validators=[validar_extensao_imagem, validar_tamanho_imagem],
    )
    ordem = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "foto do evento"
        verbose_name_plural = "fotos do evento"
        ordering = ("ordem", "id")

    def __str__(self) -> str:
        return f"Foto {self.ordem + 1} de {self.evento}"


class PresencaAtivaManager(models.Manager):
    """Esconde as presenças retiradas pelo organizador (listas, contagens, ``evento.presencas``)."""

    def get_queryset(self):
        return super().get_queryset().filter(removida_em__isnull=True)


class PresencaEvento(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="presencas", verbose_name="usuário",
    )
    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name="presencas", verbose_name="evento",
    )
    data_confirmacao = models.DateTimeField("data de confirmação", auto_now_add=True)
    # Retirada pelo embaixador/membro com cargo: o registro fica para impedir que a
    # pessoa confirme de novo no mesmo evento (até ser readmitida).
    removida_em = models.DateTimeField("retirada em", null=True, blank=True)
    removida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="retirada por",
    )

    objects = PresencaAtivaManager()
    todas = models.Manager()

    class Meta:
        base_manager_name = "todas"
        verbose_name = "presença em evento"
        verbose_name_plural = "presenças em eventos"
        ordering = ("-data_confirmacao",)
        constraints = [
            models.UniqueConstraint(fields=["usuario", "evento"], name="uq_presenca_usuario_evento"),
        ]

    def __str__(self) -> str:
        return f"{self.usuario} confirmou {self.evento}"
