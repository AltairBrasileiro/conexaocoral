"""Fluxo de moderação (aprovar/rejeitar) compartilhado por várias entidades."""
from __future__ import annotations

import logging

from core.exceptions import PermissaoNegadaError, RegraNegocioError
from core.models import StatusAprovacao, Usuario
from core.models.base import AprovavelModel

logger = logging.getLogger(__name__)


class AprovacaoService:
    """Serviço genérico para qualquer ``AprovavelModel``."""

    @staticmethod
    def _exigir_admin(usuario: Usuario) -> None:
        if not usuario.is_admin:
            raise PermissaoNegadaError("Apenas administradores podem moderar cadastros.")

    def alterar_status(self, instancia: AprovavelModel, novo_status: str, *, moderador: Usuario) -> AprovavelModel:
        self._exigir_admin(moderador)
        if instancia.status_aprovacao == novo_status:
            raise RegraNegocioError(f"O registro já está com status {novo_status}.", codigo="status_inalterado")

        campos = ["status_aprovacao"]
        instancia.status_aprovacao = novo_status

        # Selo de verificado não pode sobreviver a uma rejeição (ver CheckConstraint do Aliado).
        if novo_status != StatusAprovacao.APROVADO and getattr(instancia, "selo_verificado", False):
            instancia.selo_verificado = False
            campos.append("selo_verificado")

        instancia.save(update_fields=campos)
        logger.info(
            "%s #%s -> %s por %s", instancia.__class__.__name__, instancia.pk, novo_status, moderador.email,
        )
        return instancia

    def aprovar(self, instancia: AprovavelModel, *, moderador: Usuario) -> AprovavelModel:
        return self.alterar_status(instancia, StatusAprovacao.APROVADO, moderador=moderador)

    def rejeitar(self, instancia: AprovavelModel, *, moderador: Usuario) -> AprovavelModel:
        return self.alterar_status(instancia, StatusAprovacao.REJEITADO, moderador=moderador)
