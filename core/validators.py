"""Validadores reutilizáveis em models e serializers."""
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

DOMINIOS_WHATSAPP = frozenset({"wa.me", "api.whatsapp.com", "chat.whatsapp.com", "whatsapp.com", "www.whatsapp.com"})
DOMINIOS_INSTAGRAM = frozenset({"instagram.com", "www.instagram.com"})

validar_telefone = RegexValidator(
    regex=r"^\+?\d{10,15}$",
    message="Informe o telefone apenas com dígitos (10 a 15), opcionalmente com '+'. Ex.: +5583999999999",
)


def _dominio(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def validar_link_whatsapp(valor: str) -> None:
    """Garante que o link aponta para um domínio oficial do WhatsApp."""
    if valor and _dominio(valor) not in DOMINIOS_WHATSAPP:
        raise ValidationError("Informe um link válido do WhatsApp (ex.: https://wa.me/5583999999999).")


def validar_link_instagram(valor: str) -> None:
    """Garante que o link aponta para o Instagram."""
    if valor and _dominio(valor) not in DOMINIOS_INSTAGRAM:
        raise ValidationError("Informe um link válido do Instagram (ex.: https://instagram.com/seu_perfil).")
