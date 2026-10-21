"""Camada de acesso a dados (Repository Pattern)."""
from core.repositories.aliado_repository import AliadoRepository
from core.repositories.checkin_repository import CheckInRepository
from core.repositories.consulado_repository import ConsuladoRepository, MembroConsuladoRepository
from core.repositories.evento_repository import EventoRepository, PresencaEventoRepository
from core.repositories.partida_repository import PartidaRepository
from core.repositories.token_repository import TokenWhitelistRepository
from core.repositories.usuario_repository import UsuarioRepository

__all__ = [
    "AliadoRepository",
    "CheckInRepository",
    "ConsuladoRepository",
    "EventoRepository",
    "MembroConsuladoRepository",
    "PartidaRepository",
    "PresencaEventoRepository",
    "TokenWhitelistRepository",
    "UsuarioRepository",
]
