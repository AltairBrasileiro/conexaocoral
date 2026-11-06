"""
Código Pix estático ("copia e cola") e QR Code em SVG.

Segue o BR Code do Banco Central (padrão EMV): campos ID + tamanho + valor,
terminando com o CRC16-CCITT. A chave, o nome e a cidade vêm de
``settings.CONEXAO_CORAL["PIX"]``.
"""
from __future__ import annotations

import unicodedata
from decimal import Decimal

import qrcode
import qrcode.image.svg


def _campo(identificador: str, valor: str) -> str:
    return f"{identificador}{len(valor):02d}{valor}"


def _sem_acentos(texto: str, limite: int) -> str:
    """O BR Code aceita só ASCII; nome até 25 e cidade até 15 caracteres."""
    limpo = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return limpo.upper()[:limite]


def _crc16(dados: str) -> str:
    crc = 0xFFFF
    for byte in dados.encode():
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def codigo_pix(*, chave: str, nome: str, cidade: str, valor: Decimal | None = None, identificador: str = "***") -> str:
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", chave)
    partes = [
        _campo("00", "01"),
        _campo("26", conta),
        _campo("52", "0000"),
        _campo("53", "986"),  # real brasileiro
    ]
    if valor:
        partes.append(_campo("54", f"{valor:.2f}"))
    partes += [
        _campo("58", "BR"),
        _campo("59", _sem_acentos(nome, 25)),
        _campo("60", _sem_acentos(cidade, 15)),
        _campo("62", _campo("05", identificador)),
    ]
    sem_crc = "".join(partes) + "6304"
    return sem_crc + _crc16(sem_crc)


def qr_svg(conteudo: str) -> str:
    """QR Code como SVG embutível na página (sem imagem externa)."""
    imagem = qrcode.make(conteudo, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    return imagem.to_string(encoding="unicode")
