"""Configuração da app de interface web (páginas renderizadas pelo Django)."""
from django.apps import AppConfig


class WebConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "web"
    verbose_name = "Conexão Coral - Interface web"
