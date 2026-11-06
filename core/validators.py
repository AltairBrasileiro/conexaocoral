"""Validadores reutilizáveis em models e serializers."""
from pathlib import PurePosixPath
from urllib.parse import urlparse
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator
from django.utils import timezone

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


TAMANHO_MAXIMO_IMAGEM_MB = 5
validar_extensao_imagem = FileExtensionValidator(
    allowed_extensions=["jpg", "jpeg", "png", "webp"],
    message="Envie uma imagem JPG, PNG ou WebP.",
)


def validar_tamanho_imagem(arquivo) -> None:
    if arquivo and arquivo.size > TAMANHO_MAXIMO_IMAGEM_MB * 1024 * 1024:
        raise ValidationError(f"A imagem deve ter no máximo {TAMANHO_MAXIMO_IMAGEM_MB} MB.")


def _caminho_aleatorio(pasta: str, nome_original: str) -> str:
    """``pasta/AAAA/MM/<uuid>.<ext>``: não expõe o nome original do arquivo e evita colisões."""
    extensao = PurePosixPath(nome_original).suffix.lower() or ".jpg"
    return f"{pasta}/{timezone.now():%Y/%m}/{uuid4().hex}{extensao}"


def upload_foto_consulado(instancia, nome_original: str) -> str:
    return _caminho_aleatorio("consulados", nome_original)


def upload_imagem_evento(instancia, nome_original: str) -> str:
    return _caminho_aleatorio("eventos", nome_original)


def upload_captura_reporte(instancia, nome_original: str) -> str:
    return _caminho_aleatorio("reportes", nome_original)
