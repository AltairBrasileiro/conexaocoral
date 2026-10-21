"""Configuração da app principal do Conexão Coral."""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Conexão Coral"

    def ready(self) -> None:
        # Registra a extensão OpenAPI da autenticação customizada.
        # Import tardio: o registro acontece como efeito colateral do import.
        from core import schema  # noqa: F401
