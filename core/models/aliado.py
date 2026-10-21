"""Model de Aliado (negócios parceiros da torcida)."""
from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models.base import AprovavelModel
from core.models.choices import CategoriaAliado, StatusAprovacao
from core.validators import validar_link_instagram, validar_link_whatsapp


class Aliado(AprovavelModel):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="aliados", verbose_name="usuário",
    )
    nome_negocio = models.CharField("nome do negócio", max_length=150)
    categoria = models.CharField("categoria", max_length=20, choices=CategoriaAliado.choices, db_index=True)
    descricao = models.TextField("descrição", blank=True)
    link_instagram = models.URLField("link do Instagram", blank=True, validators=[validar_link_instagram])
    link_whatsapp = models.URLField("link do WhatsApp", blank=True, validators=[validar_link_whatsapp])
    selo_verificado = models.BooleanField("selo verificado", default=False)

    class Meta:
        verbose_name = "aliado"
        verbose_name_plural = "aliados"
        ordering = ("nome_negocio",)
        constraints = [
            # Só aliados aprovados podem ostentar o selo de verificado.
            models.CheckConstraint(
                condition=Q(selo_verificado=False) | Q(status_aprovacao=StatusAprovacao.APROVADO),
                name="ck_aliado_selo_somente_aprovado",
            ),
        ]

    def __str__(self) -> str:
        return self.nome_negocio
