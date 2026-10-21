from __future__ import annotations

from django.db.models import Count, Exists, OuterRef, Q, QuerySet

from core.models import Evento, MembroConsulado, PresencaEvento, StatusAprovacao, Usuario
from core.repositories.base import BaseRepository


class EventoRepository(BaseRepository[Evento]):
    model = Evento

    def get_queryset(self) -> QuerySet[Evento]:
        return super().get_queryset().select_related("consulado", "consulado__responsavel")

    def visiveis_para(self, usuario: Usuario) -> QuerySet[Evento]:
        """
        Regras de visibilidade:
          * Admin vê todos.
          * Responsável vê todos os eventos dos seus consulados (qualquer status).
          * Demais: apenas aprovados; os exclusivos só aparecem para membros.
        """
        qs = self.get_queryset()
        if not usuario.is_admin:
            eh_membro = Exists(
                MembroConsulado.objects.filter(consulado=OuterRef("consulado_id"), usuario=usuario)
            )
            publico_ou_membro = Q(exclusivo_membros=False) | Q(eh_membro_organizador=True)
            qs = qs.annotate(eh_membro_organizador=eh_membro).filter(
                (Q(status_aprovacao=StatusAprovacao.APROVADO) & publico_ou_membro)
                | Q(consulado__responsavel=usuario)
            )
        return qs.annotate(
            total_confirmados=Count("presencas", distinct=True),
            confirmado=Exists(PresencaEvento.objects.filter(evento=OuterRef("pk"), usuario=usuario)),
        )


class PresencaEventoRepository(BaseRepository[PresencaEvento]):
    model = PresencaEvento

    def get_queryset(self) -> QuerySet[PresencaEvento]:
        return super().get_queryset().select_related("usuario", "evento", "evento__consulado")

    def visiveis_para(self, usuario: Usuario) -> QuerySet[PresencaEvento]:
        qs = self.get_queryset()
        return qs if usuario.is_admin else qs.filter(usuario=usuario)

    def do_evento(self, evento: Evento) -> QuerySet[PresencaEvento]:
        return self.get_queryset().filter(evento=evento)
