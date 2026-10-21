from __future__ import annotations

from django.db.models import Count, Exists, OuterRef, Q, QuerySet

from core.models import Consulado, MembroConsulado, StatusAprovacao, Usuario
from core.repositories.base import BaseRepository


class ConsuladoRepository(BaseRepository[Consulado]):
    model = Consulado

    def get_queryset(self) -> QuerySet[Consulado]:
        return super().get_queryset().select_related("responsavel").prefetch_related("fotos")

    def visiveis_para(self, usuario: Usuario) -> QuerySet[Consulado]:
        """
        Admin vê tudo; demais usuários veem os aprovados e os que administram.

        Anota ``total_membros`` e ``eh_membro`` para evitar N+1 no serializer.
        """
        qs = self.get_queryset()
        if not usuario.is_admin:
            qs = qs.filter(Q(status_aprovacao=StatusAprovacao.APROVADO) | Q(responsavel=usuario))
        return qs.annotate(
            total_membros=Count("filiacoes", distinct=True),
            eh_membro=Exists(MembroConsulado.objects.filter(consulado=OuterRef("pk"), usuario=usuario)),
        )


class MembroConsuladoRepository(BaseRepository[MembroConsulado]):
    model = MembroConsulado

    def get_queryset(self) -> QuerySet[MembroConsulado]:
        return super().get_queryset().select_related("usuario", "consulado")

    def eh_membro(self, usuario: Usuario, consulado_id: int) -> bool:
        return self.model.objects.filter(usuario=usuario, consulado_id=consulado_id).exists()

    def obter_ou_criar(self, usuario: Usuario, consulado: Consulado) -> tuple[MembroConsulado, bool]:
        # get_or_create já trata IntegrityError em caso de corrida (usa savepoint).
        return self.model.objects.get_or_create(usuario=usuario, consulado=consulado)

    def membros_do_consulado(self, consulado: Consulado) -> QuerySet[MembroConsulado]:
        return self.get_queryset().filter(consulado=consulado)

    def remover_filiacao(self, usuario: Usuario, consulado: Consulado) -> int:
        removidos, _ = self.model.objects.filter(usuario=usuario, consulado=consulado).delete()
        return removidos
