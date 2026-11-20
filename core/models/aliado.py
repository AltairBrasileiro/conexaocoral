"""Model de Aliado (negócios parceiros da torcida)."""
from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models.base import AprovavelModel
from core.models.choices import CategoriaAliado, StatusAprovacao
from core.validators import (
    upload_foto_aliado, upload_perfil_aliado, validar_extensao_imagem, validar_link_instagram, validar_link_whatsapp,
    validar_tamanho_imagem,
)


class Aliado(AprovavelModel):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="aliados", verbose_name="usuário",
    )
    nome_negocio = models.CharField("nome do negócio", max_length=150)
    categoria = models.CharField("categoria", max_length=20, choices=CategoriaAliado.choices, db_index=True)
    descricao = models.TextField("descrição", blank=True)
    link_instagram = models.URLField("link do Instagram", blank=True, validators=[validar_link_instagram])
    link_whatsapp = models.URLField("link do WhatsApp", blank=True, validators=[validar_link_whatsapp])
    link_site = models.URLField("site", blank=True)
    # Foto de perfil (logo) que aparece no círculo ao lado do nome; sem ela, mostra o ícone da categoria.
    foto_perfil = models.ImageField(
        "foto de perfil", upload_to=upload_perfil_aliado, blank=True,
        validators=[validar_extensao_imagem, validar_tamanho_imagem],
    )
    # Foto que apresenta o negócio na Vitrine da Torcida (opcional).
    foto = models.ImageField(
        "foto do negócio", upload_to=upload_foto_aliado, blank=True,
        validators=[validar_extensao_imagem, validar_tamanho_imagem],
    )
    selo_verificado = models.BooleanField("selo verificado", default=False)
    # Preenchido pelo administrador ao recusar o cadastro (o dono vê em "Meus negócios").
    motivo_rejeicao = models.TextField("motivo da rejeição", blank=True)

    class Meta:
        verbose_name = "aliado"
        verbose_name_plural = "aliados"
        ordering = ("nome_negocio",)
        constraints = [
            # Só aliados aprovados podem ostentar o selo de verificado.
            models.CheckConstraint(
                check=Q(selo_verificado=False) | Q(status_aprovacao=StatusAprovacao.APROVADO),
                name="ck_aliado_selo_somente_aprovado",
            ),
        ]

    def __str__(self) -> str:
        return self.nome_negocio

    @property
    def foto_url(self) -> str:
        return self.foto.url if self.foto else ""

    @property
    def foto_perfil_url(self) -> str:
        return self.foto_perfil.url if self.foto_perfil else ""
