"""Camada de acesso a dados (Repository Pattern)."""
from core.repositories.aliado_repository import AliadoRepository
from core.repositories.carona_repository import CaronaRepository, ReservaCaronaRepository
from core.repositories.consulado_repository import (
    ConsuladoRepository,
    FotoConsuladoRepository,
    MembroConsuladoRepository,
    SolicitacaoMembroRepository,
)
from core.repositories.evento_repository import EventoRepository, PresencaEventoRepository
from core.repositories.partida_repository import PartidaRepository
from core.repositories.token_repository import TokenWhitelistRepository
from core.repositories.usuario_repository import UsuarioRepository

__all__ = [
    "AliadoRepository",
    "CaronaRepository",
    "ConsuladoRepository",
    "EventoRepository",
    "FotoConsuladoRepository",
    "MembroConsuladoRepository",
    "PartidaRepository",
    "PresencaEventoRepository",
    "ReservaCaronaRepository",
    "SolicitacaoMembroRepository",
    "TokenWhitelistRepository",
    "UsuarioRepository",
]
