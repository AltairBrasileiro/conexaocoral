from __future__ import annotations

from rest_framework import serializers

from core.models import Consulado, Partida


class PartidaSerializer(serializers.ModelSerializer):
    mando_campo_display = serializers.CharField(source="get_mando_campo_display", read_only=True)

    class Meta:
        model = Partida
        fields = (
            "id", "adversario", "mando_campo", "mando_campo_display",
            "campeonato", "data_hora", "canal_transmissao",
        )
        read_only_fields = ("id",)


class PartidaResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partida
        fields = ("id", "adversario", "mando_campo", "campeonato", "data_hora")
        read_only_fields = fields


class RankingConsuladoSerializer(serializers.ModelSerializer):
    total_checkins = serializers.IntegerField(read_only=True)

    class Meta:
        model = Consulado
        fields = ("id", "nome", "total_checkins")
        read_only_fields = fields
