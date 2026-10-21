"""FilterSets (django-filter) usados nos ViewSets."""
from __future__ import annotations

import django_filters as filters
from django.db.models import QuerySet

from core.models import Aliado, CheckIn, Consulado, Evento, Partida


class ConsuladoFilter(filters.FilterSet):
    nome = filters.CharFilter(lookup_expr="icontains")
    sou_membro = filters.BooleanFilter(method="filtrar_sou_membro", label="Apenas consulados dos quais sou membro")
    sou_responsavel = filters.BooleanFilter(method="filtrar_sou_responsavel", label="Apenas os que administro")

    class Meta:
        model = Consulado
        fields = ("status_aprovacao",)

    def filtrar_sou_membro(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        if value is None:
            return queryset
        filtro = {"filiacoes__usuario": self.request.user}
        return queryset.filter(**filtro) if value else queryset.exclude(**filtro)

    def filtrar_sou_responsavel(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        if value is None:
            return queryset
        return queryset.filter(responsavel=self.request.user) if value else queryset.exclude(responsavel=self.request.user)


class PartidaFilter(filters.FilterSet):
    campeonato = filters.CharFilter(lookup_expr="icontains")
    adversario = filters.CharFilter(lookup_expr="icontains")
    data_inicio = filters.IsoDateTimeFilter(field_name="data_hora", lookup_expr="gte")
    data_fim = filters.IsoDateTimeFilter(field_name="data_hora", lookup_expr="lte")

    class Meta:
        model = Partida
        fields = ("mando_campo",)


class CheckInFilter(filters.FilterSet):
    class Meta:
        model = CheckIn
        fields = ("partida", "consulado", "ativo")


class EventoFilter(filters.FilterSet):
    titulo = filters.CharFilter(lookup_expr="icontains")
    data_inicio = filters.IsoDateTimeFilter(field_name="data_hora_inicio", lookup_expr="gte")
    data_fim = filters.IsoDateTimeFilter(field_name="data_hora_inicio", lookup_expr="lte")

    class Meta:
        model = Evento
        fields = ("consulado", "status_aprovacao", "exclusivo_membros")


class AliadoFilter(filters.FilterSet):
    nome_negocio = filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Aliado
        fields = ("categoria", "status_aprovacao", "selo_verificado")
