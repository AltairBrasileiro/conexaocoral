"""
Pacote de models.

Todos os models são reexportados aqui para que o Django os descubra
(``core.models``) e para permitir ``from core.models import Consulado``.
"""
from core.models.aliado import Aliado
from core.models.checkin import CheckIn
from core.models.choices import CategoriaAliado, MandoCampo, StatusAprovacao, TipoUsuario
from core.models.consulado import Consulado, FotoConsulado, MembroConsulado
from core.models.evento import Evento, PresencaEvento
from core.models.partida import Partida
from core.models.token_whitelist import TokenWhitelist
from core.models.usuario import Usuario

__all__ = [
    "Aliado",
    "CategoriaAliado",
    "CheckIn",
    "Consulado",
    "Evento",
    "FotoConsulado",
    "MandoCampo",
    "MembroConsulado",
    "Partida",
    "PresencaEvento",
    "StatusAprovacao",
    "TipoUsuario",
    "TokenWhitelist",
    "Usuario",
]
