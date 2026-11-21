"""
Envia o e-mail de parabéns aos aniversariantes do dia.

Agende uma vez por dia (no cPanel: "Cron Jobs"), de preferência às 8h:
    python manage.py enviar_parabens

Rodar mais de uma vez no mesmo dia não repete o e-mail. Para testar outra data:
    python manage.py enviar_parabens --data 2026-11-21
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from core.services import AniversarioService


class Command(BaseCommand):
    help = "Envia o e-mail de parabéns aos aniversariantes do dia."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--data", help="Data no formato AAAA-MM-DD (padrão: hoje).")

    def handle(self, *args, **options) -> None:
        dia = None
        if options["data"]:
            try:
                dia = date.fromisoformat(options["data"])
            except ValueError as erro:
                raise CommandError("Use a data no formato AAAA-MM-DD.") from erro
        enviados = AniversarioService().enviar_emails(dia)
        self.stdout.write(self.style.SUCCESS(f"{enviados} e-mail(s) de parabéns enviado(s)."))
