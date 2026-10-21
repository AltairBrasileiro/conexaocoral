from __future__ import annotations

from typing import Any

from django.db import transaction

from core.exceptions import PermissaoNegadaError, RegraNegocioError
from core.models import Aliado, StatusAprovacao, Usuario
from core.repositories import AliadoRepository


class AliadoService:
    def __init__(self, repositorio: AliadoRepository | None = None) -> None:
        self.repositorio = repositorio or AliadoRepository()

    @staticmethod
    def validar_criacao(usuario: Usuario) -> None:
        if not (usuario.is_admin or usuario.is_responsavel_aliado):
            raise PermissaoNegadaError("Apenas responsáveis por aliados podem cadastrar negócios.")

    @transaction.atomic
    def criar_aliado(self, usuario: Usuario, **dados: Any) -> Aliado:
        self.validar_criacao(usuario)
        status = StatusAprovacao.APROVADO if usuario.is_admin else StatusAprovacao.PENDENTE
        return self.repositorio.criar(usuario=usuario, status_aprovacao=status, **dados)

    @transaction.atomic
    def atualizar_aliado(self, aliado: Aliado, usuario: Usuario, **dados: Any) -> Aliado:
        # Edição feita pelo dono em cadastro aprovado volta para moderação e perde o selo.
        if not usuario.is_admin and aliado.aprovado and dados:
            dados.update(status_aprovacao=StatusAprovacao.PENDENTE, selo_verificado=False)
        return self.repositorio.atualizar(aliado, **dados)

    def definir_selo(self, aliado: Aliado, *, verificado: bool, moderador: Usuario) -> Aliado:
        if not moderador.is_admin:
            raise PermissaoNegadaError("Apenas administradores podem gerenciar o selo de verificado.")
        if verificado and not aliado.aprovado:
            raise RegraNegocioError("Só aliados aprovados podem receber o selo de verificado.")
        if aliado.selo_verificado == verificado:
            raise RegraNegocioError("O selo já está neste estado.", codigo="status_inalterado")
        return self.repositorio.atualizar(aliado, selo_verificado=verificado)
