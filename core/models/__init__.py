"""
Pacote de models.

Todos os models são reexportados aqui para que o Django os descubra
(``core.models``) e para permitir ``from core.models import Consulado``.
"""
from core.models.aliado import Aliado
from core.models.choices import CategoriaAliado, MandoCampo, StatusAprovacao, TipoUsuario
from core.models.consulado import Consulado, FotoConsulado, MembroConsulado, SolicitacaoMembro
from core.models.evento import Evento, FotoEvento, PresencaEvento
from core.models.partida import Partida
from core.models.reporte import Reporte
from core.models.token_whitelist import TokenWhitelist
from core.models.usuario import Usuario

__all__ = [
    "Aliado",
    "CategoriaAliado",
    "Consulado",
    "Evento",
    "FotoConsulado",
    "FotoEvento",
    "MandoCampo",
    "MembroConsulado",
    "Partida",
    "PresencaEvento",
    "Reporte",
    "SolicitacaoMembro",
    "StatusAprovacao",
    "TipoUsuario",
    "TokenWhitelist",
    "Usuario",
]
