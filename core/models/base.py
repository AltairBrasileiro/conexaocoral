"""Models abstratos reutilizados pelas entidades concretas."""
from django.db import models

from core.models.choices import StatusAprovacao


class TimeStampedModel(models.Model):
    """Adiciona ``criado_em`` preenchido automaticamente na criação."""

    criado_em = models.DateTimeField("criado em", auto_now_add=True, editable=False)

    class Meta:
        abstract = True


class AprovavelModel(TimeStampedModel):
    """Entidade sujeita a moderação pelo administrador."""

    status_aprovacao = models.CharField(
        "status de aprovação",
        max_length=10,
        choices=StatusAprovacao.choices,
        default=StatusAprovacao.PENDENTE,
        db_index=True,
    )

    class Meta:
        abstract = True

    @property
    def aprovado(self) -> bool:
        return self.status_aprovacao == StatusAprovacao.APROVADO
