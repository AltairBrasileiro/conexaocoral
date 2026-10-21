"""
Regras de negócio de eventos e confirmações de presença.

* Só o responsável pelo consulado (ou admin) cria/edita eventos do consulado.
* Eventos de consulados não aprovados não podem ser criados.
* Presença só pode ser confirmada por MEMBROS do consulado organizador,
  em eventos aprovados e ainda não encerrados.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.exceptions import (
    ConflitoError,
    PermissaoNegadaError,
    RecursoNaoEncontradoError,
    RegraNegocioError,
)
from core.models import Consulado, Evento, PresencaEvento, StatusAprovacao, Usuario
from core.repositories import EventoRepository, MembroConsuladoRepository, PresencaEventoRepository


class EventoService:
    def __init__(
        self,
        repositorio: EventoRepository | None = None,
        presenca_repositorio: PresencaEventoRepository | None = None,
        membro_repositorio: MembroConsuladoRepository | None = None,
    ) -> None:
        self.repositorio = repositorio or EventoRepository()
        self.presenca_repositorio = presenca_repositorio or PresencaEventoRepository()
        self.membro_repositorio = membro_repositorio or MembroConsuladoRepository()

    # ------------------------------------------------------------------ eventos
    @staticmethod
    def validar_dados_evento(
        usuario: Usuario,
        consulado: Consulado,
        inicio: datetime,
        fim: datetime,
        *,
        instancia: Evento | None = None,
    ) -> None:
        if not usuario.is_admin and consulado.responsavel_id != usuario.id:
            raise PermissaoNegadaError(
                "Apenas o responsável pelo consulado pode gerenciar seus eventos.", campo="consulado",
            )
        if not consulado.aprovado:
            raise RegraNegocioError("O consulado precisa estar aprovado para ter eventos.", campo="consulado")
        if fim <= inicio:
            raise RegraNegocioError("O fim deve ser posterior ao início.", campo="data_hora_fim")
        # Na criação (ou ao remarcar), não aceitamos eventos no passado.
        inicio_alterado = instancia is None or instancia.data_hora_inicio != inicio
        if inicio_alterado and inicio < timezone.now():
            raise RegraNegocioError("O evento não pode começar no passado.", campo="data_hora_inicio")

    @transaction.atomic
    def criar_evento(self, usuario: Usuario, **dados: Any) -> Evento:
        self.validar_dados_evento(usuario, dados["consulado"], dados["data_hora_inicio"], dados["data_hora_fim"])
        status = StatusAprovacao.APROVADO if usuario.is_admin else StatusAprovacao.PENDENTE
        return self.repositorio.criar(status_aprovacao=status, **dados)

    @transaction.atomic
    def atualizar_evento(self, evento: Evento, usuario: Usuario, **dados: Any) -> Evento:
        inicio = dados.get("data_hora_inicio", evento.data_hora_inicio)
        fim = dados.get("data_hora_fim", evento.data_hora_fim)
        self.validar_dados_evento(usuario, evento.consulado, inicio, fim, instancia=evento)
        dados.pop("consulado", None)  # o consulado organizador não muda

        # Alterações relevantes em evento aprovado voltam para moderação (exceto admin).
        campos_sensiveis = {"titulo", "descricao", "data_hora_inicio", "data_hora_fim"}
        if not usuario.is_admin and evento.aprovado and campos_sensiveis & dados.keys():
            dados["status_aprovacao"] = StatusAprovacao.PENDENTE
        return self.repositorio.atualizar(evento, **dados)

    # ---------------------------------------------------------------- presenças
    def validar_confirmacao(self, usuario: Usuario, evento: Evento) -> None:
        if not evento.aprovado:
            raise RegraNegocioError("Este evento ainda não foi aprovado.", campo="evento")
        if evento.data_hora_fim <= timezone.now():
            raise RegraNegocioError("Este evento já foi encerrado.", campo="evento")
        if not self.membro_repositorio.eh_membro(usuario, evento.consulado_id):
            raise PermissaoNegadaError(
                "Apenas membros do consulado organizador podem confirmar presença. "
                "Faça check-in no consulado em dia de jogo para se tornar membro.",
                campo="evento",
            )
        if self.presenca_repositorio.existe(usuario=usuario, evento=evento):
            raise ConflitoError("Você já confirmou presença neste evento.", campo="evento")

    @transaction.atomic
    def confirmar_presenca(self, usuario: Usuario, evento: Evento) -> PresencaEvento:
        self.validar_confirmacao(usuario, evento)
        try:
            with transaction.atomic():
                return self.presenca_repositorio.criar(usuario=usuario, evento=evento)
        except IntegrityError as exc:
            raise ConflitoError("Você já confirmou presença neste evento.", campo="evento") from exc

    def cancelar_presenca(self, presenca: PresencaEvento, usuario: Usuario) -> None:
        if presenca.usuario_id != usuario.id and not usuario.is_admin:
            raise PermissaoNegadaError("Você só pode cancelar as suas próprias confirmações.")
        if presenca.evento.data_hora_inicio <= timezone.now():
            raise RegraNegocioError("Não é possível cancelar a presença após o início do evento.")
        self.presenca_repositorio.remover(presenca)

    def obter_presenca(self, presenca_id: int) -> PresencaEvento:
        presenca = self.presenca_repositorio.obter_por_id(presenca_id)
        if presenca is None:
            raise RecursoNaoEncontradoError("Confirmação de presença não encontrada.")
        return presenca
