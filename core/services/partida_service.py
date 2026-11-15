"""
Regras de negócio das partidas.

O calendário é público para quem está logado; só administradores cadastram,
editam e excluem partidas.
"""
from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from core.exceptions import PermissaoNegadaError, RegraNegocioError
from core.models import Partida, Usuario
from core.repositories import PartidaRepository


class PartidaService:
    def __init__(self, repositorio: PartidaRepository | None = None) -> None:
        self.repositorio = repositorio or PartidaRepository()

    def proximas_partidas(self, limite: int = 10) -> QuerySet[Partida]:
        return self.repositorio.proximas(limite)

    @staticmethod
    def _exigir_admin(usuario: Usuario) -> None:
        if not usuario.is_admin:
            raise PermissaoNegadaError("Apenas administradores gerenciam o calendário de partidas.")

    @staticmethod
    def _limpar(dados: dict[str, Any]) -> dict[str, Any]:
        for campo in ("adversario", "campeonato", "canal_transmissao"):
            if campo in dados:
                dados[campo] = (dados[campo] or "").strip()
        for campo, mensagem in (("adversario", "Informe o adversário."), ("campeonato", "Informe o campeonato.")):
            if campo in dados and not dados[campo]:
                raise RegraNegocioError(mensagem, campo=campo)
        return dados

    def criar_partida(self, admin: Usuario, **dados: Any) -> Partida:
        self._exigir_admin(admin)
        return self.repositorio.criar(**self._limpar(dados))

    def atualizar_partida(self, admin: Usuario, partida: Partida, **dados: Any) -> Partida:
        self._exigir_admin(admin)
        return self.repositorio.atualizar(partida, **self._limpar(dados))

    def excluir_partida(self, admin: Usuario, partida: Partida) -> None:
        self._exigir_admin(admin)
        self.repositorio.remover(partida)
