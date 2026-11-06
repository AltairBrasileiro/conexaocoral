"""Model de Reporte: problema ou sugestão enviada por um usuário (visível só para admins)."""
from django.conf import settings
from django.db import models

from core.validators import upload_captura_reporte, validar_extensao_imagem, validar_tamanho_imagem


class Reporte(models.Model):
    class Tipo(models.TextChoices):
        PROBLEMA = "PROBLEMA", "Problema"
        SUGESTAO = "SUGESTAO", "Sugestão"

    class Status(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        RESOLVIDO = "RESOLVIDO", "Resolvido"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="reportes",
        verbose_name="enviado por",
    )
    tipo = models.CharField("tipo", max_length=10, choices=Tipo.choices, default=Tipo.PROBLEMA, db_index=True)
    mensagem = models.TextField("mensagem")
    # Página em que o usuário estava ao abrir o formulário (ajuda a reproduzir o problema).
    pagina = models.CharField("página", max_length=300, blank=True)
    captura = models.ImageField(
        "captura de tela", upload_to=upload_captura_reporte, blank=True,
        validators=[validar_extensao_imagem, validar_tamanho_imagem],
    )
    status = models.CharField("status", max_length=10, choices=Status.choices, default=Status.ABERTO, db_index=True)
    criado_em = models.DateTimeField("enviado em", auto_now_add=True)
    resolvido_em = models.DateTimeField("resolvido em", null=True, blank=True)
    resolvido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="resolvido por",
    )

    class Meta:
        verbose_name = "reporte"
        verbose_name_plural = "reportes"
        ordering = ("-criado_em",)

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} #{self.pk} ({self.get_status_display()})"
