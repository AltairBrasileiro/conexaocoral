"""Enumerações (choices) compartilhadas pelos models."""
from django.db import models


class TipoUsuario(models.TextChoices):
    """Papéis (roles) usados no controle de acesso."""

    TORCEDOR = "TORCEDOR", "Torcedor"
    RESPONSAVEL_CONSULADO = "RESPONSAVEL_CONSULADO", "Responsável por Consulado"
    RESPONSAVEL_ALIADO = "RESPONSAVEL_ALIADO", "Responsável por Aliado"
    ADMIN = "ADMIN", "Administrador"


class StatusAprovacao(models.TextChoices):
    """Fluxo de moderação de consulados, eventos e aliados."""

    PENDENTE = "PENDENTE", "Pendente"
    APROVADO = "APROVADO", "Aprovado"
    REJEITADO = "REJEITADO", "Rejeitado"


class MandoCampo(models.TextChoices):
    CASA = "CASA", "Casa"
    FORA = "FORA", "Fora"


class CategoriaAliado(models.TextChoices):
    BAR = "BAR", "Bar"
    RESTAURANTE = "RESTAURANTE", "Restaurante"
    LOJA = "LOJA", "Loja"
    VESTUARIO = "VESTUARIO", "Vestuário"
    SERVICOS = "SERVICOS", "Serviços"
    OUTROS = "OUTROS", "Outros"
