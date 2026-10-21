"""
Remove da whitelist os tokens já expirados.

Agende periodicamente (cron, Celery beat...):
    python manage.py limpar_tokens_expirados
"""
from django.core.management.base import BaseCommand

from core.services import TokenWhitelistService


class Command(BaseCommand):
    help = "Remove tokens JWT expirados da whitelist."

    def handle(self, *args, **options) -> None:
        removidos = TokenWhitelistService().limpar_expirados()
        self.stdout.write(self.style.SUCCESS(f"{removidos} token(s) expirado(s) removido(s)."))
