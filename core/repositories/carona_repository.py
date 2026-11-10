from __future__ import annotations

from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from django.utils import timezone

from core.models import Carona, MembroConsulado, ReservaCarona, Usuario
from core.repositories.base import BaseRepository


class CaronaRepository(BaseRepository[Carona]):
    model = Carona

    def get_queryset(self) -> QuerySet[Carona]:
        return super().get_queryset().select_related("consulado", "motorista")

    def visiveis_para(self, usuario: Usuario) -> QuerySet[Carona]:
        """
        Regras de visibilidade:
          * Admin vê todas.
          * Quem oferece, o embaixador do consulado e os passageiros veem a carona sempre.
          * Demais membros do consulado: só enquanto a oferta não expira.
          * Quem não é membro não vê nenhuma.

        Anota ``total_reservas`` e ``reservado`` (o usuário tem vaga) para evitar N+1.
        """
        qs = self.get_queryset()
        reservado = Exists(ReservaCarona.objects.filter(carona=OuterRef("pk"), usuario=usuario))
        if not usuario.is_admin:
            eh_membro = Exists(MembroConsulado.objects.filter(consulado=OuterRef("consulado_id"), usuario=usuario))
            qs = qs.annotate(eh_membro_consulado=eh_membro, reservado=reservado).filter(
                Q(motorista=usuario)
                | Q(consulado__responsavel=usuario)
                | Q(reservado=True)
                | (Q(eh_membro_consulado=True) & Q(expira_em__gt=timezone.now()))
            )
        else:
            qs = qs.annotate(reservado=reservado)
        # Count faz o JOIN direto no banco: o filtro das retiradas precisa ser explícito.
        return qs.annotate(
            total_reservas=Count("reservas", filter=Q(reservas__removida_em__isnull=True), distinct=True),
        )


class ReservaCaronaRepository(BaseRepository[ReservaCarona]):
    model = ReservaCarona

    def get_queryset(self) -> QuerySet[ReservaCarona]:
        return super().get_queryset().select_related("usuario", "carona", "carona__consulado", "carona__motorista")

    def da_carona(self, carona: Carona) -> QuerySet[ReservaCarona]:
        return self.get_queryset().filter(carona=carona)

    def do_usuario(self, usuario: Usuario) -> QuerySet[ReservaCarona]:
        return self.get_queryset().filter(usuario=usuario)

    def retiradas_da_carona(self, carona: Carona) -> QuerySet[ReservaCarona]:
        return (
            ReservaCarona.todas.filter(carona=carona, removida_em__isnull=False)
            .select_related("usuario", "removida_por")
        )

    def foi_retirado(self, usuario: Usuario, carona: Carona) -> bool:
        return ReservaCarona.todas.filter(carona=carona, usuario=usuario, removida_em__isnull=False).exists()

    def obter_retirada(self, pk: int) -> ReservaCarona | None:
        return (
            ReservaCarona.todas.filter(pk=pk, removida_em__isnull=False)
            .select_related("usuario", "carona", "carona__consulado").first()
        )
