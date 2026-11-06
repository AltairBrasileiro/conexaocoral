"""Models de Consulado e da associação N:N com Usuario (MembroConsulado)."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models.base import AprovavelModel
from core.models.choices import StatusAprovacao, TipoUsuario
from core.validators import (
    upload_foto_consulado, validar_extensao_imagem, validar_link_whatsapp, validar_tamanho_imagem,
)


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
    # Preenchido pelo administrador ao recusar a solicitação de cadastro.
    motivo_rejeicao = models.TextField("motivo da rejeição", blank=True)

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
    # Definido pelo embaixador (ex.: "Vice-presidente", "Tesoureiro") e exibido na página pública.
    cargo = models.CharField("cargo", max_length=60, blank=True)

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
    # A foto pode ser um arquivo enviado (ex.: na solicitação do consulado) ou um link externo.
    imagem = models.ImageField(
        "imagem", upload_to=upload_foto_consulado, blank=True,
        validators=[validar_extensao_imagem, validar_tamanho_imagem],
    )
    url = models.URLField("URL da imagem", max_length=500, blank=True)
    legenda = models.CharField("legenda", max_length=150, blank=True)
    ordem = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "foto do consulado"
        verbose_name_plural = "fotos do consulado"
        ordering = ("ordem", "id")

    def __str__(self) -> str:
        return self.legenda or self.src

    @property
    def src(self) -> str:
        """Endereço para exibir a foto: o arquivo enviado tem prioridade sobre o link."""
        return self.imagem.url if self.imagem else self.url


class SolicitacaoMembro(models.Model):
    """Pedido de um torcedor para entrar num consulado; o embaixador aprova ou recusa."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="solicitacoes_membro",
        verbose_name="usuário",
    )
    consulado = models.ForeignKey(
        Consulado, on_delete=models.CASCADE, related_name="solicitacoes_membro", verbose_name="consulado",
    )
    status_aprovacao = models.CharField(
        "status", max_length=10, choices=StatusAprovacao.choices, default=StatusAprovacao.PENDENTE, db_index=True,
    )
    criado_em = models.DateTimeField("solicitado em", auto_now_add=True)
    respondido_em = models.DateTimeField("respondido em", null=True, blank=True)
    respondido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="respondido por",
    )

    class Meta:
        verbose_name = "solicitação para ser membro"
        verbose_name_plural = "solicitações para ser membro"
        ordering = ("criado_em",)
        constraints = [
            # Um pedido em análise por vez para cada par usuário-consulado.
            models.UniqueConstraint(
                fields=["usuario", "consulado"],
                condition=models.Q(status_aprovacao="PENDENTE"),
                name="uq_solicitacao_membro_pendente",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.usuario} → {self.consulado} ({self.get_status_aprovacao_display()})"
