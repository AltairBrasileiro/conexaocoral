"""Models de Consulado e da associação N:N com Usuario (MembroConsulado)."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models.base import AprovavelModel
from core.models.choices import TipoUsuario
from core.validators import validar_link_whatsapp


class Consulado(AprovavelModel):
    """Ponto de encontro de torcedores (sede física com geolocalização)."""

    # FK gera a coluna "responsavel_id" no banco.
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # impede apagar um usuário que ainda responde por consulados
        related_name="consulados_responsavel",
        limit_choices_to={"tipo_usuario__in": [TipoUsuario.RESPONSAVEL_CONSULADO, TipoUsuario.ADMIN]},
        verbose_name="responsável",
    )
    nome = models.CharField("nome", max_length=150, unique=True)
    descricao = models.TextField("descrição", blank=True)
    endereco = models.CharField("endereço", max_length=255)
    latitude = models.DecimalField(
        "latitude", max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        "longitude", max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    link_whatsapp = models.URLField("link do WhatsApp", blank=True, validators=[validar_link_whatsapp])
    # Emblema exibido no pino do mapa; sem logo, o app usa o pino padrão.
    logo_url = models.URLField("URL do logo", max_length=500, blank=True)

    membros = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="MembroConsulado",
        related_name="consulados_filiados",
        blank=True,
    )

    class Meta:
        verbose_name = "consulado"
        verbose_name_plural = "consulados"
        ordering = ("nome",)
        indexes = [models.Index(fields=["latitude", "longitude"], name="idx_consulado_geo")]

    def __str__(self) -> str:
        return self.nome


class MembroConsulado(models.Model):
    """Tabela associativa: um usuário filiado a um consulado."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="filiacoes", verbose_name="usuário",
    )
    consulado = models.ForeignKey(
        Consulado, on_delete=models.CASCADE, related_name="filiacoes", verbose_name="consulado",
    )
    data_filiacao = models.DateTimeField("data de filiação", auto_now_add=True)

    class Meta:
        verbose_name = "membro de consulado"
        verbose_name_plural = "membros de consulado"
        ordering = ("-data_filiacao",)
        constraints = [
            # Garante unicidade do par usuário-consulado no nível do banco.
            models.UniqueConstraint(fields=["usuario", "consulado"], name="uq_membro_usuario_consulado"),
        ]

    def __str__(self) -> str:
        return f"{self.usuario} → {self.consulado}"


class FotoConsulado(models.Model):
    """Foto do bar/sede exibida na tela de detalhes do consulado."""

    consulado = models.ForeignKey(
        Consulado, on_delete=models.CASCADE, related_name="fotos", verbose_name="consulado",
    )
    url = models.URLField("URL da imagem", max_length=500)
    legenda = models.CharField("legenda", max_length=150, blank=True)
    ordem = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "foto do consulado"
        verbose_name_plural = "fotos do consulado"
        ordering = ("ordem", "id")

    def __str__(self) -> str:
        return self.legenda or self.url
