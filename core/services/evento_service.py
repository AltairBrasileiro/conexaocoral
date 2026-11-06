"""
Regras de negócio de eventos e confirmações de presença.

* Só o responsável pelo consulado (ou admin) cria/edita eventos do consulado,
  com total autonomia: o evento é publicado na hora, sem moderação.
* Eventos de consulados não aprovados não podem ser criados.
* Eventos livres aceitam a confirmação de presença de qualquer torcedor;
  os exclusivos, só de MEMBROS do consulado organizador (e nem aparecem
  para quem não é membro). Em ambos, o evento precisa estar publicado e
  ainda não encerrado.
* Cada evento pode ter até 6 fotos de divulgação.
* Limite de vagas opcional: quando todas as vagas são preenchidas, novas
  confirmações são recusadas.
* O participante pode desmarcar a própria presença até o início do evento.
* A lista de confirmados é vista (e pode ser enxugada) pelo embaixador, pelos
  membros com cargo no consulado e pelo admin.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from django.core.files import File
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.exceptions import (
    ConflitoError,
    PermissaoNegadaError,
    RecursoNaoEncontradoError,
    RegraNegocioError,
)
from core.models import Consulado, Evento, FotoEvento, PresencaEvento, StatusAprovacao, Usuario
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

    # ------------------------------------------------------------------ fotos
    MAXIMO_FOTOS = 6

    def _validar_quantidade_de_fotos(self, atuais: int, novas: int) -> None:
        if atuais + novas > self.MAXIMO_FOTOS:
            raise RegraNegocioError(
                f"Cada evento pode ter até {self.MAXIMO_FOTOS} fotos "
                f"(já tem {atuais}; você enviou {novas}).",
                campo="fotos",
            )

    def _adicionar_fotos(self, evento: Evento, fotos: list[File]) -> None:
        ultima = evento.fotos.order_by("-ordem").first()
        proxima = (ultima.ordem + 1) if ultima else 0
        for posicao, arquivo in enumerate(fotos, start=proxima):
            FotoEvento.objects.create(evento=evento, imagem=arquivo, ordem=posicao)

    @staticmethod
    def _apagar_arquivos(nomes: list[str]) -> None:
        """Apaga os arquivos só depois de a transação ser confirmada (nada se perde se der erro)."""
        if nomes:
            armazenamento = FotoEvento._meta.get_field("imagem").storage
            transaction.on_commit(lambda: [armazenamento.delete(nome) for nome in nomes])

    # ------------------------------------------------------------------ eventos
    @transaction.atomic
    def criar_evento(self, usuario: Usuario, *, fotos: list[File] | None = None, **dados: Any) -> Evento:
        self.validar_dados_evento(usuario, dados["consulado"], dados["data_hora_inicio"], dados["data_hora_fim"])
        fotos = fotos or []
        self._validar_quantidade_de_fotos(0, len(fotos))
        # O embaixador tem autonomia sobre os eventos do próprio consulado: publica na hora.
        evento = self.repositorio.criar(status_aprovacao=StatusAprovacao.APROVADO, **dados)
        self._adicionar_fotos(evento, fotos)
        return evento

    @transaction.atomic
    def atualizar_evento(
        self,
        evento: Evento,
        usuario: Usuario,
        *,
        fotos_novas: list[File] | None = None,
        remover_fotos: list[int] | None = None,
        **dados: Any,
    ) -> Evento:
        inicio = dados.get("data_hora_inicio", evento.data_hora_inicio)
        fim = dados.get("data_hora_fim", evento.data_hora_fim)
        self.validar_dados_evento(usuario, evento.consulado, inicio, fim, instancia=evento)
        dados.pop("consulado", None)  # o consulado organizador não muda
        limite = dados.get("limite_vagas")
        if limite:
            confirmados = self.presenca_repositorio.do_evento(evento).count()
            if limite < confirmados:
                raise RegraNegocioError(
                    f"O evento já tem {confirmados} presenças confirmadas: o limite não pode ser menor que isso.",
                    campo="limite_vagas",
                )
        removidas = list(evento.fotos.filter(pk__in=remover_fotos or []))
        fotos_novas = fotos_novas or []
        self._validar_quantidade_de_fotos(evento.fotos.count() - len(removidas), len(fotos_novas))

        evento = self.repositorio.atualizar(evento, **dados)
        nomes = [foto.imagem.name for foto in removidas]
        FotoEvento.objects.filter(pk__in=[foto.pk for foto in removidas]).delete()
        self._apagar_arquivos(nomes)
        self._adicionar_fotos(evento, fotos_novas)
        return evento

    @transaction.atomic
    def excluir_evento(self, evento: Evento, usuario: Usuario) -> None:
        if not usuario.is_admin and evento.consulado.responsavel_id != usuario.id:
            raise PermissaoNegadaError("Apenas o responsável pelo consulado pode excluir seus eventos.")
        nomes = [foto.imagem.name for foto in evento.fotos.all()]
        self.repositorio.remover(evento)
        self._apagar_arquivos(nomes)

    # ---------------------------------------------------------------- presenças
    def validar_confirmacao(self, usuario: Usuario, evento: Evento) -> None:
        if not evento.aprovado:
            raise RegraNegocioError("Este evento não está publicado.", campo="evento")
        if evento.data_hora_fim <= timezone.now():
            raise RegraNegocioError("Este evento já foi encerrado.", campo="evento")
        if evento.exclusivo_membros and not self.membro_repositorio.eh_membro(usuario, evento.consulado_id):
            raise PermissaoNegadaError(
                "Este evento é exclusivo para membros do consulado. "
                "Peça para entrar no consulado: o embaixador aprova os novos membros.",
                campo="evento",
            )
        if PresencaEvento.todas.filter(usuario=usuario, evento=evento, removida_em__isnull=False).exists():
            raise PermissaoNegadaError(
                "A organização do consulado retirou a sua presença deste evento.", campo="evento",
            )
        if self.presenca_repositorio.existe(usuario=usuario, evento=evento):
            raise ConflitoError("Você já confirmou presença neste evento.", campo="evento")
        if evento.limite_vagas and self.presenca_repositorio.do_evento(evento).count() >= evento.limite_vagas:
            raise RegraNegocioError("As vagas deste evento já foram preenchidas.", campo="evento", codigo="esgotado")

    @transaction.atomic
    def confirmar_presenca(self, usuario: Usuario, evento: Evento) -> PresencaEvento:
        # Trava o evento: duas pessoas disputando a última vaga não passam juntas (PostgreSQL).
        if evento.limite_vagas:
            evento = Evento.objects.select_for_update().select_related("consulado").get(pk=evento.pk)
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

    # ------------------------------------------------------- lista de presença
    def pode_gerir_presencas_do_consulado(self, usuario: Usuario, consulado: Consulado) -> bool:
        """Embaixador, membro com cargo no consulado ou admin."""
        return (
            usuario.is_admin
            or consulado.responsavel_id == usuario.id
            or self.membro_repositorio.tem_cargo(usuario, consulado.id)
        )

    def pode_gerir_presencas(self, usuario: Usuario, evento: Evento) -> bool:
        return self.pode_gerir_presencas_do_consulado(usuario, evento.consulado)

    def exigir_gestor_de_presencas(self, usuario: Usuario, evento: Evento) -> None:
        if not self.pode_gerir_presencas(usuario, evento):
            raise PermissaoNegadaError(
                "Apenas o embaixador e os membros com cargo no consulado veem a lista de confirmados."
            )

    def remover_presenca(self, gestor: Usuario, presenca: PresencaEvento) -> None:
        """
        O organizador tira alguém da lista de confirmados (a qualquer momento).

        O registro é mantido como "retirado" para a pessoa não confirmar de novo.
        """
        self.exigir_gestor_de_presencas(gestor, presenca.evento)
        self.presenca_repositorio.atualizar(presenca, removida_em=timezone.now(), removida_por=gestor)

    @transaction.atomic
    def readmitir_presenca(self, gestor: Usuario, presenca: PresencaEvento) -> PresencaEvento:
        """Devolve à lista alguém que foi retirado (respeitando o limite de vagas)."""
        evento = Evento.objects.select_for_update().select_related("consulado").get(pk=presenca.evento_id)
        self.exigir_gestor_de_presencas(gestor, evento)
        if evento.limite_vagas and self.presenca_repositorio.do_evento(evento).count() >= evento.limite_vagas:
            raise RegraNegocioError("Todas as vagas estão preenchidas: libere uma antes de readmitir alguém.")
        return self.presenca_repositorio.atualizar(presenca, removida_em=None, removida_por=None)

    def obter_presenca(self, presenca_id: int) -> PresencaEvento:
        presenca = self.presenca_repositorio.obter_por_id(presenca_id)
        if presenca is None:
            raise RecursoNaoEncontradoError("Confirmação de presença não encontrada.")
        return presenca
