from __future__ import annotations

from typing import Any

from django.db import transaction

from core.exceptions import PermissaoNegadaError, RecursoNaoEncontradoError, RegraNegocioError
from core.models import Consulado, StatusAprovacao, Usuario
from core.repositories import ConsuladoRepository, MembroConsuladoRepository


class ConsuladoService:
    def __init__(
        self,
        repositorio: ConsuladoRepository | None = None,
        membro_repositorio: MembroConsuladoRepository | None = None,
    ) -> None:
        self.repositorio = repositorio or ConsuladoRepository()
        self.membro_repositorio = membro_repositorio or MembroConsuladoRepository()

    @staticmethod
    def validar_criacao(usuario: Usuario) -> None:
        if not (usuario.is_admin or usuario.is_responsavel_consulado):
            raise PermissaoNegadaError("Apenas responsáveis por consulado podem cadastrar consulados.")

    @transaction.atomic
    def criar_consulado(self, usuario: Usuario, **dados: Any) -> Consulado:
        self.validar_criacao(usuario)
        # Cadastros feitos por admin já nascem aprovados; os demais passam por moderação.
        status = StatusAprovacao.APROVADO if usuario.is_admin else StatusAprovacao.PENDENTE
        consulado = self.repositorio.criar(responsavel=usuario, status_aprovacao=status, **dados)
        # O responsável é automaticamente membro do próprio consulado.
        self.membro_repositorio.obter_ou_criar(usuario, consulado)
        return consulado

    def sair_do_consulado(self, usuario: Usuario, consulado: Consulado) -> None:
        if consulado.responsavel_id == usuario.id:
            raise RegraNegocioError("O responsável não pode deixar o próprio consulado.")
        if not self.membro_repositorio.remover_filiacao(usuario, consulado):
            raise RecursoNaoEncontradoError("Você não é membro deste consulado.")
