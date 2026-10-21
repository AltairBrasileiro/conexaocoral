"""
Regras de negócio de check-in.

1. Um usuário só pode ter 1 check-in ATIVO por partida.
2. O primeiro check-in em um consulado filia o usuário automaticamente
   (cria ``MembroConsulado``).
3. Check-in só em consulado aprovado e dentro da janela da partida.
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.exceptions import ConflitoError, PermissaoNegadaError, RegraNegocioError
from core.models import CheckIn, Consulado, Partida, Usuario
from core.repositories import CheckInRepository, MembroConsuladoRepository


class CheckInService:
    def __init__(
        self,
        repositorio: CheckInRepository | None = None,
        membro_repositorio: MembroConsuladoRepository | None = None,
    ) -> None:
        self.repositorio = repositorio or CheckInRepository()
        self.membro_repositorio = membro_repositorio or MembroConsuladoRepository()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _validar_janela(partida: Partida) -> None:
        config = getattr(settings, "CONEXAO_CORAL", {})
        horas_antes = config.get("CHECKIN_HORAS_ANTES", 0)
        horas_depois = config.get("CHECKIN_HORAS_DEPOIS", 0)
        if not (horas_antes or horas_depois):
            return  # janela desativada

        agora = timezone.now()
        abertura = partida.data_hora - timedelta(hours=horas_antes)
        encerramento = partida.data_hora + timedelta(hours=horas_depois)
        if not abertura <= agora <= encerramento:
            raise RegraNegocioError(
                f"O check-in fica disponível de {horas_antes}h antes até {horas_depois}h após o início da partida.",
                campo="partida",
                codigo="fora_da_janela",
            )

    # ---------------------------------------------------------------- validação
    def validar_checkin(self, usuario: Usuario, partida: Partida, consulado: Consulado) -> None:
        """Validações usadas tanto pelo serializer quanto pelo próprio serviço."""
        if not consulado.aprovado:
            raise RegraNegocioError("Só é possível fazer check-in em consulados aprovados.", campo="consulado")
        self._validar_janela(partida)
        if self.repositorio.existe_ativo(usuario, partida):
            raise ConflitoError("Você já possui um check-in ativo para esta partida.", campo="partida")

    # ------------------------------------------------------------------ comandos
    @transaction.atomic
    def realizar_checkin(self, usuario: Usuario, partida: Partida, consulado: Consulado) -> CheckIn:
        self.validar_checkin(usuario, partida, consulado)
        try:
            # Savepoint: se o índice único parcial disparar (requisições simultâneas),
            # desfazemos só este trecho e devolvemos um erro de domínio.
            with transaction.atomic():
                checkin = self.repositorio.criar(usuario=usuario, partida=partida, consulado=consulado)
        except IntegrityError as exc:
            raise ConflitoError("Você já possui um check-in ativo para esta partida.", campo="partida") from exc

        # Filiação automática no primeiro check-in (idempotente).
        self.membro_repositorio.obter_ou_criar(usuario, consulado)
        return checkin

    def cancelar_checkin(self, checkin: CheckIn, usuario: Usuario) -> CheckIn:
        if checkin.usuario_id != usuario.id and not usuario.is_admin:
            raise PermissaoNegadaError("Você só pode cancelar os seus próprios check-ins.")
        if not checkin.ativo:
            raise RegraNegocioError("Este check-in já foi cancelado.")
        # A filiação ao consulado é mantida: ela representa vínculo, não presença.
        return self.repositorio.atualizar(checkin, ativo=False)
