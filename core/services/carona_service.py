"""
Regras de negócio da Carona Coral.

* Oferecem carona num consulado: o administrador, o embaixador do consulado e
  os membros com cargo atribuído pelo embaixador.
* A carona tem vagas (1 a 50), um texto de até 500 caracteres, a data e hora
  do encontro e o prazo da oferta (até o horário do encontro).
* Só membros do consulado veem a carona e reservam vaga, e só enquanto a
  oferta não expira. Quem oferece não reserva vaga na própria carona.
* O passageiro pode cancelar a própria reserva até o horário do encontro.
* Quem oferece a carona (e também o embaixador e o admin) edita, exclui,
  retira passageiros, faz o check-in e exporta a lista em PDF.
* Quem é retirado da carona não consegue reservar de novo nela, a não ser que
  seja readmitido (mesma regra da lista de presença dos eventos).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.exceptions import ConflitoError, PermissaoNegadaError, RegraNegocioError
from core.models import Carona, Consulado, ReservaCarona, Usuario
from core.models.carona import MAXIMO_CARACTERES_CARONA, MAXIMO_VAGAS_CARONA
from core.repositories import CaronaRepository, MembroConsuladoRepository, ReservaCaronaRepository


class CaronaService:
    MAXIMO_VAGAS = MAXIMO_VAGAS_CARONA
    MAXIMO_CARACTERES = MAXIMO_CARACTERES_CARONA

    def __init__(
        self,
        repositorio: CaronaRepository | None = None,
        reserva_repositorio: ReservaCaronaRepository | None = None,
        membro_repositorio: MembroConsuladoRepository | None = None,
    ) -> None:
        self.repositorio = repositorio or CaronaRepository()
        self.reserva_repositorio = reserva_repositorio or ReservaCaronaRepository()
        self.membro_repositorio = membro_repositorio or MembroConsuladoRepository()

    # ------------------------------------------------------------ permissões
    def pode_oferecer(self, usuario: Usuario, consulado: Consulado) -> bool:
        """Administrador, embaixador do consulado ou membro com cargo atribuído pelo embaixador."""
        return (
            usuario.is_admin
            or consulado.responsavel_id == usuario.id
            or self.membro_repositorio.tem_cargo(usuario, consulado.id)
        )

    @staticmethod
    def pode_gerir(usuario: Usuario, carona: Carona) -> bool:
        """Quem oferece a carona, o embaixador do consulado ou o administrador."""
        return usuario.is_admin or carona.motorista_id == usuario.id or carona.consulado.responsavel_id == usuario.id

    def exigir_gestor(self, usuario: Usuario, carona: Carona) -> None:
        if not self.pode_gerir(usuario, carona):
            raise PermissaoNegadaError("Apenas quem oferece a carona e o embaixador do consulado podem gerenciá-la.")

    # ------------------------------------------------------------ validação
    def _validar_dados(
        self,
        consulado: Consulado,
        *,
        descricao: str,
        vagas: int,
        encontro: datetime,
        expira_em: datetime,
        instancia: Carona | None = None,
    ) -> None:
        if not consulado.aprovado:
            raise RegraNegocioError("O consulado precisa estar aprovado para ter caronas.", campo="consulado")
        if not descricao:
            raise RegraNegocioError("Escreva os detalhes da carona.", campo="descricao")
        if len(descricao) > self.MAXIMO_CARACTERES:
            raise RegraNegocioError(
                f"O texto pode ter no máximo {self.MAXIMO_CARACTERES} caracteres.", campo="descricao",
            )
        if not 1 <= vagas <= self.MAXIMO_VAGAS:
            raise RegraNegocioError(f"Ofereça de 1 a {self.MAXIMO_VAGAS} vagas.", campo="vagas")
        agora = timezone.now()
        # Na criação (ou ao remarcar), datas no passado não são aceitas.
        if (instancia is None or instancia.data_hora_encontro != encontro) and encontro <= agora:
            raise RegraNegocioError("O encontro não pode ser no passado.", campo="data_hora_encontro")
        if (instancia is None or instancia.expira_em != expira_em) and expira_em <= agora:
            raise RegraNegocioError("O prazo da oferta precisa ser no futuro.", campo="expira_em")
        if expira_em > encontro:
            raise RegraNegocioError(
                "A oferta precisa expirar até o horário do encontro.", campo="expira_em",
            )
        if instancia is not None:
            reservas = self.reserva_repositorio.da_carona(instancia).count()
            if vagas < reservas:
                raise RegraNegocioError(
                    f"A carona já tem {reservas} vaga(s) reservada(s): não dá para oferecer menos que isso.",
                    campo="vagas",
                )

    # ---------------------------------------------------------------- ofertas
    def criar_carona(self, usuario: Usuario, consulado: Consulado, **dados: Any) -> Carona:
        if not self.pode_oferecer(usuario, consulado):
            raise PermissaoNegadaError(
                "Apenas o embaixador e os membros com cargo no consulado podem oferecer caronas.",
            )
        dados["descricao"] = (dados.get("descricao") or "").strip()
        self._validar_dados(
            consulado, descricao=dados["descricao"], vagas=dados["vagas"],
            encontro=dados["data_hora_encontro"], expira_em=dados["expira_em"],
        )
        return self.repositorio.criar(consulado=consulado, motorista=usuario, **dados)

    @transaction.atomic
    def atualizar_carona(self, carona: Carona, usuario: Usuario, **dados: Any) -> Carona:
        self.exigir_gestor(usuario, carona)
        # Trava a carona: ninguém reserva enquanto as vagas estão sendo alteradas.
        carona = Carona.objects.select_for_update().select_related("consulado").get(pk=carona.pk)
        dados.pop("consulado", None)  # o consulado e quem oferece não mudam
        dados.pop("motorista", None)
        if "descricao" in dados:
            dados["descricao"] = (dados["descricao"] or "").strip()
        self._validar_dados(
            carona.consulado,
            descricao=dados.get("descricao", carona.descricao),
            vagas=dados.get("vagas", carona.vagas),
            encontro=dados.get("data_hora_encontro", carona.data_hora_encontro),
            expira_em=dados.get("expira_em", carona.expira_em),
            instancia=carona,
        )
        return self.repositorio.atualizar(carona, **dados)

    def excluir_carona(self, carona: Carona, usuario: Usuario) -> None:
        self.exigir_gestor(usuario, carona)
        self.repositorio.remover(carona)

    # --------------------------------------------------------------- reservas
    @staticmethod
    def expirada(carona: Carona) -> bool:
        return carona.expira_em <= timezone.now()

    @transaction.atomic
    def reservar(self, usuario: Usuario, carona: Carona) -> ReservaCarona:
        # Trava a carona: duas pessoas disputando a última vaga não passam juntas (PostgreSQL).
        carona = Carona.objects.select_for_update().select_related("consulado").get(pk=carona.pk)
        if carona.motorista_id == usuario.id:
            raise RegraNegocioError("Você é quem oferece esta carona.")
        if not self.membro_repositorio.eh_membro(usuario, carona.consulado_id):
            raise PermissaoNegadaError("A Carona Coral é exclusiva para membros do consulado.")
        if self.expirada(carona):
            raise RegraNegocioError("Esta oferta de carona já expirou.")
        if self.reserva_repositorio.foi_retirado(usuario, carona):
            raise PermissaoNegadaError("Quem oferece esta carona retirou a sua reserva.")
        if self.reserva_repositorio.existe(carona=carona, usuario=usuario):
            raise ConflitoError("Você já reservou uma vaga nesta carona.")
        if self.reserva_repositorio.da_carona(carona).count() >= carona.vagas:
            raise RegraNegocioError("As vagas desta carona já foram preenchidas.", codigo="esgotado")
        try:
            with transaction.atomic():
                return self.reserva_repositorio.criar(carona=carona, usuario=usuario)
        except IntegrityError as exc:
            raise ConflitoError("Você já reservou uma vaga nesta carona.") from exc

    def cancelar_reserva(self, usuario: Usuario, reserva: ReservaCarona) -> None:
        if reserva.usuario_id != usuario.id:
            raise PermissaoNegadaError("Você só pode cancelar as suas próprias reservas.")
        if reserva.carona.data_hora_encontro <= timezone.now():
            raise RegraNegocioError("Não é possível cancelar a reserva depois do horário do encontro.")
        self.reserva_repositorio.remover(reserva)

    def retirar_passageiro(self, gestor: Usuario, reserva: ReservaCarona) -> ReservaCarona:
        """
        Quem oferece a carona libera a vaga de um passageiro.

        O registro é mantido como "retirado" para a pessoa não reservar de novo.
        """
        self.exigir_gestor(gestor, reserva.carona)
        if reserva.checkin_em:
            raise RegraNegocioError("Desfaça o check-in antes de retirar o passageiro da carona.")
        return self.reserva_repositorio.atualizar(reserva, removida_em=timezone.now(), removida_por=gestor)

    @transaction.atomic
    def readmitir_passageiro(self, gestor: Usuario, reserva: ReservaCarona) -> ReservaCarona:
        """Devolve à carona quem foi retirado (respeitando as vagas)."""
        carona = Carona.objects.select_for_update().select_related("consulado").get(pk=reserva.carona_id)
        self.exigir_gestor(gestor, carona)
        if self.reserva_repositorio.da_carona(carona).count() >= carona.vagas:
            raise RegraNegocioError("Todas as vagas estão ocupadas: libere uma antes de readmitir alguém.")
        return self.reserva_repositorio.atualizar(reserva, removida_em=None, removida_por=None)

    # --------------------------------------------------------------- check-in
    def registrar_checkin(self, gestor: Usuario, reserva: ReservaCarona) -> ReservaCarona:
        self.exigir_gestor(gestor, reserva.carona)
        if reserva.checkin_em:
            raise ConflitoError(f"O check-in de {reserva.usuario.nome} já foi feito.")
        return self.reserva_repositorio.atualizar(reserva, checkin_em=timezone.now(), checkin_por=gestor)

    def desfazer_checkin(self, gestor: Usuario, reserva: ReservaCarona) -> ReservaCarona:
        self.exigir_gestor(gestor, reserva.carona)
        return self.reserva_repositorio.atualizar(reserva, checkin_em=None, checkin_por=None)
